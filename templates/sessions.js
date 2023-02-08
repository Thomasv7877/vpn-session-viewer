var socket = io("", {
   transports: ["polling", "websocket"],
   rememberUpgrade: true
});

socket.on('connect', function () {
   console.log("user from cookie: " + '{{ selectedUser }}');
});

var authenticated = '{{authenticated}}';
console.log("authenticated: " + authenticated);

addEventListener('pageshow', (e) => { // reconnect neemt +-30 sec bij page back, workaround is window reload als back evt gedetecteerd
   if(e.persisted == true){
      window.location.reload()
   }
});

if(authenticated == 'True'){
   var fadeDiv = document.getElementById("fadeToggle")
   fadeDiv.classList.remove("fadeToggle");
   var authPrompt = document.getElementById("authPrompt")
   authPrompt.style.zIndex = -1;
   authPrompt.style.visibility = 'hidden';
}

var userList = document.getElementsByName('users');
userList[0].value = '{{selectedUser}}';
userList[0].onchange = function (e) {
   this.form.submit() // via post methode
}

function setTimeConnected(parentNode, timeSince, newUser) {
   var connectedAt = new Date(timeSince.trim()).getTime(); // voorloop spatie moet getrimmed worden, anders NaN fout in Firefox bij page reload
   var x = setInterval(function () {
      var currentUser = parentNode.childNodes[5].innerHTML;
      // enkel uitvoeren als username waarde zelfde is als toen methode origineel werd uitgevoerd
      if (currentUser === newUser) {
         var now = new Date().getTime();
         var distance = now - connectedAt;
         var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
         var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
         var seconds = Math.floor((distance % (1000 * 60)) / 1000);
         parentNode.childNodes[7].innerHTML = hours + "h " + minutes + "m " + seconds + "s ";
      } else {
         clearInterval(x);
      }
   }, 1000);
}

// tabellen kleuren on converteren naar timer
var sessionList = document.getElementsByTagName('tr');
for (let i = 1; i < sessionList.length; i++) { // va index 1 overlopen anders header rij ook
   if (sessionList[i].childNodes[5].innerHTML != 'None') {
      sessionList[i].className = "table-secondary";
      setTimeConnected(sessionList[i], sessionList[i].childNodes[7].innerHTML, sessionList[i].childNodes[5].innerHTML);
   }
}

document.getElementById("sessions").addEventListener("click", function (e) {
   if (e.target && e.target.nodeName == "TD") {
      var ch = e.target.parentNode.childNodes
      socket.emit('sessie_klik', {
         zh: ch[1].innerHTML,
         cName: ch[3].innerHTML,
         user: ch[5].innerHTML,
         conn_at: ch[7].innerHTML
      }, userList[0].value);
   }
});

socket.on('updateList', function (data) {
   var sessionList = document.getElementsByTagName('tr');
   for (let i = 0; i < sessionList.length; i++) {
      if (sessionList[i].childNodes[3].innerHTML === data[0][1]) {
         if (data[0][2] == null) { // als user = null mag verwijderd worden uit lijst
            sessionList[i].childNodes[5].innerHTML = 'None';
            sessionList[i].childNodes[7].innerHTML = 'None';
            sessionList[i].className = "";
         } else {
            sessionList[i].childNodes[5].innerHTML = data[0][2];
            setTimeConnected(sessionList[i], data[0][3], data[0][2]);
            sessionList[i].className = "table-secondary";
         }
      }
   }
});