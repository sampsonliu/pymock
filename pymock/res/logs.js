var wsStatus = document.getElementById('wsStatus');
var logPanel = document.getElementById('logPanel');
var schema = 'ws';
if (location.protocol == 'https:') {
    schema = 'wss';
}
var ws = new WebSocket(`${schema}://${location.host}/ws/logs`);
ws.onopen = onOpen;
ws.onclose = onClose;
ws.onmessage = onMessage;

function onOpen() {
    wsStatus.innerText = 'connected';
}

function onClose(e) {
    wsStatus.innerText = 'disconnected';
}

function onMessage(msg) {
    appendLog(msg.data);
}

function appendLog(log) {
    var pre = document.createElement('pre');
    pre.innerText = log;
    logPanel.appendChild(pre);
}