var currentPath = '.';
var filePath = $('#filePath');
var fileList = $('#fileList');
var currentFile = $('#currentFile');
var modeSelect = $('#modeSelect');
var saveButton = $('#saveButton');
var reloadButton = $('#reloadButton');
var newFolderButton = $('#newFolderButton');
var newFileButton = $('#newFileButton');
var entries = null;
var fileNamePattern = /^[A-Za-z0-9_\-.]+$/
fileList.on('click', onFileListClicked);
listFiles(currentPath);

var editor = ace.edit("editor");
editor.setTheme('ace/theme/chrome');
editor.setFontSize(16);
editor.session.setMode('ace/mode/plain_text');
var modeMap = {
    'txt': 'plain_text',
    'json': 'json',
    'py': 'python'
};
initModeSelect();
var sessionFile = '';
var sessionDirty = false;
editor.session.on('change', function() {
    sessionDirty = true;
    saveButton.removeAttr('disabled');
});
window.addEventListener("beforeunload", function (e) {
    if (sessionDirty) {
        var msg = `file ${sessionFile} is modified, ignore?`;
        (e || window.event).returnValue = msg;
        return msg;
    }
});

saveButton.on('click', function() {
    if (sessionFile) {
        saveFile(sessionFile);
    }
});
reloadButton.on('click', function() {
    if (sessionFile) {
        reloadFile(sessionFile);
    }
});
newFolderButton.on('click', function() {
    createFile('folder');
});
newFileButton.on('click', function() {
    createFile('file');
});

function onFileListClicked(event) {
    var entryidx = $(event.target).data('entryidx');
    if (entryidx !== undefined) {
        var entry = entries[entryidx];
        if (entry.type == 'dir') {
            listFiles(entry.path);
        } else if (entry.type == 'file') {
            editFile(entry.path, entry.name);
        }
    }
}

function reportError(e) {
    if (e.status == 0) {
        alert('server disconnected');
    } else {
        alert(`${e.status} ${e.statusText}\n${e.responseText}`);
    }
}

function saveFile(path) {
    $.ajax({
        method: 'PUT',
        url: '/file?path=' + encodeURIComponent(path),
        data: editor.session.getValue(),
        contentType: 'text/plain'
    })
    .done(function() {
        sessionDirty = false;
        saveButton.attr('disabled', true);
    })
    .fail(reportError);
}

function reloadFile(path) {
    $.post('/file/reload?path=' + encodeURIComponent(path), function(message) {
        alert(message);
    }).fail(reportError);
}

function initModeSelect() {
    var options = ''
    for (var key in modeMap) {
        var mode = modeMap[key];
        options += `<option value="${mode}">${mode}</option>`
    }
    modeSelect.html(options);
    modeSelect.on('change', function() {
        editor.session.setMode('ace/mode/' + modeSelect.val());
    })
}

function fileExt(name) {
    var idx = name.lastIndexOf('.');
    if (idx != -1) {
        return name.substr(idx + 1);
    }
    return null;
}

function getFileMode(name) {
    var ext = fileExt(name);
    if (ext in modeMap) {
        return modeMap[ext];
    }
    return 'plain_text';
}

function checkSession() {
    if (sessionDirty) {
        return confirm(`file ${sessionFile} is modified, ignore?`);
    }
    return true;
}

function editFile(path, name) {
    if (!checkSession()) {
        return;
    }
    $.get('/file?path=' + encodeURIComponent(path), function(data) {
        sessionFile = path;
        currentFile.html(sessionFile);
        editor.session.setValue(data);
        modeSelect.val(getFileMode(name));
        modeSelect.change();
        sessionDirty = false;
        saveButton.attr('disabled', true);
    }).fail(reportError);
}

function entryHtml(entry, idx) {
    var icon = `<i class="fas ${entry.type=='dir'? 'fa-folder' : 'fa-file'}"></i>`;
    return `<li data-entryidx="${idx}">${icon} ${entry.name}</li>`;
}

function listFiles(path) {
    $.get('/file/list?path=' + encodeURIComponent(path), function(data) {
        currentPath = data.current_path;
        entries = data.entries;
        var content = '';
        for (var idx in data.entries) {
            entry = data.entries[idx];
            content += entryHtml(entry, idx);
        }
        fileList.html(content);
        filePath.html(currentPath);
    }).fail(reportError)
}

function createFile(type) {
    var fileName = prompt(`New ${type} name`);
    if (!fileName) {
        return;
    }
    if (!fileNamePattern.test(fileName)) {
        alert('File name should only contain [A-Za-z0-9_\-.]');
        return;
    }
    $.post('/file?path=' + encodeURIComponent(currentPath) + '&type=' + type + '&name=' + fileName, function() {
        listFiles(currentPath);
    }).fail(reportError);
}
