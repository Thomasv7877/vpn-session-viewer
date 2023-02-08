from flask import Flask, jsonify, render_template, request, redirect, send_from_directory, url_for, make_response, session, current_app
import sqlite3 as sql
from flask_socketio import SocketIO
import datetime
import csv
import pytz
import logging
import sys
import os
import api
import time

app = Flask(__name__)
app.register_blueprint(api.bp, url_prefix='/api')
#app.config["SESSION_PERMANENT"] = True # onnodig
app.config["SECRET_KEY"] = 'secret'
socketio = SocketIO(app)
socketio.server_options['transports'] = ['polling', 'websocket'] # omkeren om niet te upgraden, direct websocket ipv upgrade maar werkt niet icm azure
auditPath = app.root_path + '/audit_export/'

def getSecret():
    return app.config["SECRET_KEY"]

# sessies (zh, sub entry) ophalen uit csv file
def getSessions():
    with open('./config/sessions.csv', mode = 'r') as file:
        sessionsCSV = csv.reader(file, delimiter=';')
        sessionsList = [tuple(row) for row in sessionsCSV]
        return sessionsList

# bij start van app - sqlite db init, bestaande data droppen
def createDB():
    try:
        with sql.connect('database.db') as con:
            con.execute('DROP TABLE if exists sessions;')
            con.execute('CREATE TABLE sessions (hospitalname text,connectionname text unique, username text, connected_at text)')
            con.commit()
    except:
        con.rollback()
    finally:
         con.close()

# na init db seeden via getSessions(), returnt 2d array die via 1 query 'executemany' geinsert kan worden
def seedDB():
      try:
         with sql.connect("database.db") as con:
            cur = con.cursor()
            sessions = getSessions()

            cur.executemany("INSERT INTO sessions (hospitalname, connectionname) VALUES (?,?)", sessions)
            con.commit()
      except:
         con.rollback()
      finally:
         con.close()

# users lezen uit txt file
def getUsers():
    a = []
    with open('./config/users.txt', 'r') as file:
        a = file.read().splitlines()
    return a

# sessies uit db lezen, user ophalen uit cookie, users uit file lezen en lijst template renderen met vorige getUsers() als args
@app.route('/')
@app.route('/sessions')
def list():
    try:
        with sql.connect("database.db") as con:
            con.row_factory = sql.Row
            cur = con.cursor()
            cur.execute("select * from sessions")
            rows = cur.fetchall()

            username = request.cookies.get('username')
            #authenticated = request.cookies.get('authenticated')
            token = request.cookies.get('token')
            authenticated = api.authenticate(token)
    except:
         con.rollback()
    finally:
         con.close()   

    return render_template("sessions.html",rows = rows, selectedUser = username, users = getUsers(), authenticated = authenticated)

# verwerkt onchange event op user lijst in sessions.html, geklikte user opgeslaan in cookie
# opm! niet mogelijk via socket.io omdat bij instellen cookie een response gegeven moet worden, als antw in dit geval sessions.html herladen
@app.route('/userSelect', methods = ['POST'])
def userSelect():
    user = request.form['users']
    print(user +" gelesecteerd uit dropdown")
    resp = make_response(redirect(url_for('list')))
    resp.set_cookie('username', user, expires=datetime.datetime.now() + datetime.timedelta(days=30)) # geldigheid toevoegen anders verloren na sessie
    return resp

# verwerkt onclick event op lijst van sessies, elke td waarde uit tr meegegeven + actieve user uit dropdown
# opt 1: als selected user al in rij stond wordt deze verwijderd uit db
# opt 2: als selected user nog niet bestaat inserten in db samen met huidig moment
# op einde socket.io emit sturen om rij te herladen met nieuwe data, moet broadcast zijn om voor elke browser sessie te updaten
@socketio.on('sessie_klik')
def sessie_klik(data, selectedUser):
    time = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))
    print("Klik! User " + selectedUser + " en tijd is " + str(time.strftime('%Y-%m-%d %H:%M:%S')))
    try:
        with sql.connect("database.db") as con:
            cur = con.cursor()
            # gebruiker staat in lijn, verwijderen uit db, audit lijn schrijven
            if selectedUser == data['user']:
                cur.execute("select * from sessions where connectionname = ?", (data['cName'],))
                rij = cur.fetchone()
                writeAudit(rij, time)
                cur.execute("update sessions set username = ?, connected_at = ? where connectionname = ?", (None, None, data['cName'])) # Null werkt niet in query zelf, enkel None vanuit tuple
            # gebruiker niet in lijn (andere gebruiker of leeg), toegevoegd aan db
            else:
                cur.execute("select * from sessions where connectionname = ?", (data['cName'],))
                rij = cur.fetchone()
                # als andere user op lijn stond wordt hun sessie gesloten, een audit lijn voor wegschrijven
                if(rij[2] != 'None' and data['user'] != 'None'):
                    writeAudit(rij, time)
                cur.execute("update sessions set username = ?, connected_at = ? where connectionname = ?", (selectedUser, time, data['cName']))

            # sessies ophalen voor pagina verversing   
            cur.execute("select * from sessions where connectionname = ?", (data['cName'],)) # igv 1 arg ',' op einde tuple gebruiken, anders error..
            rows = cur.fetchall()
            con.commit()
    except:
            con.rollback()
    finally:
            con.close()

    socketio.emit('updateList', rows, broadcast=True)

# (dis)connects wegschrijven in audit.csv
def writeAudit(line, time):
    auditName = time.strftime('wk_%W_%m-%Y')
    fullPath = auditPath + auditName + ".csv"
    #print(auditPad)
    with open(fullPath, mode = 'a', newline='') as file: # newline = '' anders blanco lijn toegevoegd aan csv, mode a is voor appending, w voor nieuwe file
        auditCSV = csv.writer(file, delimiter=';')
        alsLijst = [item for item in line] # list comprehension voor conversie tuple (sqlite resultaat) naar list, alt: list(line) werkt niet
        preTime = alsLijst.pop() # = tijd in slecht formaat
        alsLijst.append(preTime[:-13]) # = tijd in goed formaat
        alsLijst.append(time.strftime('%Y-%m-%d %H:%M:%S')) # huidige tijd
        auditCSV.writerow(alsLijst)

# custom handler voor 404 (pagina niet gekend) fouten
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# is vervangen door api/slogin
@app.route('/login', methods = ['POST'])
def login():
    password = request.form['password']
    if password == app.config["SECRET_KEY"]:
        print("Auth OK")
        resp = make_response(redirect(url_for('list')))
        resp.set_cookie('authenticated', "True", expires=datetime.datetime.now() + datetime.timedelta(days=30))
        return resp
    else:
        return list()

@app.route('/reports')
def reports():
    token = request.cookies.get('token')
    authenticated = api.authenticate(token)
    #authenticated = request.cookies.get('authenticated')
    if authenticated:
        reports = os.listdir(auditPath)
        #print(reports)
        return render_template("reports.html", reports = reports)
    else:
        return list()

# file downloaden van folder buiten static of template, route nodig
@app.route('/audit_export/<path:filename>')
def audit_export(filename):
    #print("dl start: " + app.root_path + '/audit_export/' + filename)
    return send_from_directory(auditPath, filename)

# als klasse main -> lokaal gestart, anders opgeroepen met startup cmd guniconr (wss vanuit docker)
if __name__ == '__main__':
    print('Started local')
    createDB()
    seedDB()
    getSessions()
    #print('audit pad is: ' + auditPath)
    #socketio.run(app)
    api.createUserDB()
    api.seedUserDB()
    #testUser = api.getUserByName('promon')
    #print('Password is:' + testUser[3])
    #api.mailtest()
    socketio.run(app, host='0.0.0.0',port=5000) # host 0.0.0.0 = bereikbaar van buitenaf
else:
    print('Started via Docker/Azure')
    sys.stdout = sys.stderr # anders enkel errors of app.logger entries in gunicorn (vb vanuit docker) console, nu ook print statements
    gunicorn_error_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers.extend(gunicorn_error_logger.handlers)
    app.logger.setLevel(logging.INFO)
    auditPath = '/audit_export/' # audit pad buite napp structuur om volume te kunnen koppelen in azure
    createDB()
    seedDB()
    #print('audit pad is: ' + auditPath)
    getSessions()
    api.createUserDB()
    api.seedUserDB()