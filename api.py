import jwt
from werkzeug.security import generate_password_hash,check_password_hash
from functools import wraps
import uuid
import sqlite3 as sql
from flask import Blueprint, Flask, jsonify, render_template, request, redirect, send_from_directory, url_for, make_response, session, current_app
import datetime
import smtplib
from email.message import EmailMessage
import json

bp = Blueprint('api', __name__, template_folder='templates')

hc_user = "promon"
hc_pw = '12345'

mailTo = 'mail@mail.com'
mailFrom = mailUser = 'mail@mail.com'
mailPw = 'mailPassword'
mailServer = 'smtp.office365.com'
mailPort = '587'

# db met app users maken
def createUserDB():
    try:
        with sql.connect('userDatabase.db') as con:
            con.execute('DROP TABLE if exists user;')
            con.execute('CREATE TABLE user (id INTEGER PRIMARY KEY, public_id INTEGER, name text, password text)')
            con.commit()
    except:
        con.rollback()
    finally:
         con.close()

# standaard user toevoegen aan app user db, username en password hardcoded..
def seedUserDB():
      try:
         with sql.connect("userDatabase.db") as con:
            cur = con.cursor()

            hashed_password = generate_password_hash(hc_pw, method='sha256')
            userName = hc_user
            user = [(str(uuid.uuid4()), userName, hashed_password)]

            cur.executemany("INSERT INTO user (public_id, name, password) VALUES (?,?,?)", user)
            con.commit()
      except:
         con.rollback()
      finally:
         con.close()

# gebruikt bij login actie (zowel session app als api)
def getUserByName(userName):
    try:
        with sql.connect('userDatabase.db') as con:
            cur = con.cursor()
            cur.execute("select * from user where name = ?", (userName,))
            user = cur.fetchone()
            return user
    except:
        con.rollback()
    finally:
        con.close()

# gebruikt bij authenticatie (zowel session app als api)
def getUserByPublicId(publicId):
    try:
        with sql.connect('userDatabase.db') as con:
            cur = con.cursor()
            cur.execute("select * from user where public_id = ?", (publicId,))
            user = cur.fetchone()
            return user
    except:
        con.rollback()
    finally:
        con.close()    

# voor beveiligde api methodes uitgevoerd, authenticatie/token check
def token_required(f):
   @wraps(f)
   def decorator(*args, **kwargs):
       from app import getSecret # lazy loading, circulaire import vermijden
       token = None
       if 'x-access-tokens' in request.headers:
           token = request.headers['x-access-tokens']
 
       if not token:
           return jsonify({'message': 'a valid token is missing'})
       try:
           data = jwt.decode(token, getSecret(), algorithms=["HS256"])
           #current_user = Users.query.filter_by(public_id=data['public_id']).first()
           current_user = getUserByPublicId(data['public_id'])
       except:
           return jsonify({'message': 'token is invalid'})
 
       return f(current_user, *args, **kwargs)
   return decorator

# in begin beveiligded session app methodes uitgevoerd (sessie lijst en audit exports tonen), authenticatie/token in cookie check
def authenticate(token):
    from app import getSecret
    try:
        data = jwt.decode(token, getSecret(), algorithms=["HS256"])
        current_user = getUserByPublicId(data['public_id'])
        return True
    except:
        return False

# token aanvragen (api)
@bp.route('/loginUser', methods=['POST']) 
def login_user():
    from app import getSecret # lazy loading, circulaire import vermijden
    print('login called')
    auth = request.authorization  
    if not auth or not auth.username or not auth.password: 
       return make_response('could not verify', 401, {'Authentication': 'login required"'})   
 
    #user = Users.query.filter_by(name=auth.username).first()  
    user = getUserByName(auth.username)
    if check_password_hash(user[3], auth.password):
       token = jwt.encode({'public_id' : user[1], 'exp' : datetime.datetime.utcnow() + datetime.timedelta(days=7)}, getSecret(), "HS256")
 
       return jsonify({'token' : token})
 
    return make_response('could not verify',  401, {'Authentication': '"login required"'})

# token aanvragen (sessie app)
@bp.route('/slogin', methods = ['POST'])
def slogin():
    from app import getSecret
    password = request.form['password']
    user = getUserByName(hc_user)
    if check_password_hash(user[3], password):
       token = jwt.encode({'public_id' : user[1], 'exp' : datetime.datetime.utcnow() + datetime.timedelta(days=7)}, getSecret(), "HS256")
       resp = make_response(redirect(url_for('list')))
       resp.set_cookie('token', token, expires=datetime.datetime.now() + datetime.timedelta(days=7))
       return resp
    else:
        return redirect(url_for('list'))

# monitoring msg posten, inhoud json doorgestuurd naar mailbox
@bp.route('/placeMessage', methods=['POST'])
@token_required
def placeMessage(current_user):
    data = request.get_json()
    #data = request.form
    #print(request.form['message'])
    #print(data['ziekenhuis'])
    sendMail(data)
    return jsonify({'message' : 'monitoring message sent'})

# token check
@bp.route('/test', methods=['GET'])
@token_required
def test(current_user):
    return "Authorized"

# hulpmethode voor placeMessage, mail sturen
def sendMail(jsonMsg):
    # local/debug smtp server: python -m smtpd -c DebuggingServer -n localhost:1025
    message = EmailMessage()
    # content = """Beste,
    
    # multi lijn
    # Hello World!
    # """
    #content = jsonMsg

    prettyPrintedJsonMsg = json.dumps(jsonMsg, indent=4)
    message.set_content(str(prettyPrintedJsonMsg))

    message['Subject'] = 'Monitoring via vpn-sessions API'
    message['From'] = mailFrom
    message['To'] = mailTo

    #s = smtplib.SMTP('localhost:1025')
    s = smtplib.SMTP(mailServer, mailPort)
    s.starttls()
    s.login(mailUser, mailPw)
    s.send_message(message)
    s.quit()
    print('monitoring mail gestuurd')