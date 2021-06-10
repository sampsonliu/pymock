var tunnelList = $('#tunnelList');
var tunnelNameSpan = $('#tunnelName');
var connectionList = $('#connectionList');
var tunnels = [];
var currentTunnel = null;
var connections = [];
loadTunnels();

$('#tunnelRefreshButton').on('click', function() {
    loadTunnels();
});

$('#connectionRefreshButton').on('click', function() {
    loadConnections();
});

function reportError(e) {
    if (e.status == 0) {
        alert('server disconnected');
    } else {
        alert(`${e.status} ${e.statusText}\n${e.responseText}`);
    }
}

function tunnelItem(tunnel, idx) {
    return `<li class="tunnel-item" data-idx="${idx}">
    <div class="tunnel-desc">
        <span class="desc button tunnelDesc">${tunnel.name}</span>
        <span class="tag">${tunnel.status}</span>
    </div>
    <div class="tunnel-action">
        <span>
            <i class="fas fa-play-circle button tunnelPlayButton"></i>
            <i class="fas fa-stop-circle button tunnelStopButton"></i>
        </span>
    </div>
</li>`;
}

function loadTunnels() {
    $.get('/tunnel', function(data) {
        tunnels = data;
        html = '';
        tunnels.forEach((tunnel, idx) => {
            tunnel.name = `${tunnel.port}=>${tunnel.dest_host}:${tunnel.dest_port}`;
            html += tunnelItem(tunnel, idx);
        });
        tunnelList.html(html);

        $('span.tunnelDesc').on('click', tunnelClick);
        $('i.tunnelPlayButton').on('click', tunnelPlay);
        $('i.tunnelStopButton').on('click', tunnelStop);
    }).fail(reportError);
}

function tunnelClick() {
    var idx = $(this).parent().parent().data('idx');
    currentTunnel = tunnels[idx];
    loadConnections();
}

function connectionItem(conn, idx) {
    return `<li class="connection-item" data-idx="${idx}">
    <span class="desc">${conn.peer_ip}:${conn.peer_port}</span>
    <span>
        <span class="button connectionCloseButton">close</span>
        <span class="button connectionResetButton">reset</span>
    </span>
</li>`;
}

function loadConnections() {
    if (!currentTunnel) {
        return;
    }
    $.get(`/tunnel/connection?port=${currentTunnel.port}`, function(data) {
        tunnelNameSpan.text(`(${currentTunnel.name})`);
        connections = data;
        html = '';
        connections.forEach((conn, idx) => {
            html += connectionItem(conn, idx);
        });
        connectionList.html(html);
        $('span.connectionCloseButton').on('click', connectionClose);
        $('span.connectionResetButton').on('click', connectionReset);
    }).fail(reportError);
}

function tunnelAction(elem, action) {
    var idx = $(elem).parent().parent().parent().data('idx');
    var tunnel = tunnels[idx];
    $.post(`/tunnel?port=${tunnel.port}&action=${action}`, function(data) {
        loadTunnels();
    }).fail(reportError);
}

function tunnelPlay() {
    tunnelAction(this, 'start');
    return false;
}

function tunnelStop() {
    tunnelAction(this, 'stop');
    return false;
}

function connectionAction(elem, action) {
    var idx = $(elem).parent().parent().data('idx');
    var connection = connections[idx];
    $.post(`/tunnel/connection?port=${currentTunnel.port}&conn_id=${connection.conn_id}&action=${action}`, function(data) {
        loadConnections();
    }).fail(reportError);
}

function connectionClose() {
    connectionAction(this, 'close');
    return false;
}

function connectionReset() {
    connectionAction(this, 'reset');
    return false;
}
