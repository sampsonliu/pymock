from tornado import web, websocket, httpserver
import os
import json
import functools
import traceback
import asyncio
from http import HTTPStatus
import logging
import ssl
import base64

from .utils import normalize_path, randstr, socket_nolinger
from .config import reload_file, load_config
from . import tunnel

logger = logging.getLogger('pymock.controller')
log_clients = []
server_password = None


class BasicAuthHandler(web.RequestHandler):
    def _bad_auth(self):
        self.set_status(HTTPStatus.UNAUTHORIZED)
        self.set_header('WWW-Authenticate', 'Basic realm="PyMock WebUI"')
        raise web.Finish()

    def prepare(self):
        if server_password is not None:
            if not 'Authorization' in self.request.headers:
                self._bad_auth()
            auth = self.request.headers['Authorization']
            if not auth.startswith('Basic '):
                self._bad_auth()
            auth = auth[6:]
            try:
                auth = base64.decodebytes(auth.encode('ascii')).decode('ascii')
                _, password = auth.split(':')
            except:
                self._bad_auth()
            if server_password != password:
                self._bad_auth()


class CommonRequestHandler(BasicAuthHandler):
    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'text/plain')
        if "exc_info" in kwargs:
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(line)
            self.finish()
        else:
            self.finish(f'{status_code} {self._reason}')

    def write_json(self, obj):
        self.set_header('Content-Type', 'application/json')
        self.set_header('Cache-control', 'no-cache')
        self.write(json.dumps(obj))

    def write_text(self, text):
        self.set_header('Content-Type', 'text/plain')
        self.set_header('Cache-control', 'no-cache')
        self.write(text)

    def compute_etag(self):
        return None


class FileWithAuthHandler(BasicAuthHandler, web.StaticFileHandler):
    pass


class FileCommonHandler(CommonRequestHandler):
    def initialize(self):
        self.path = None

    def prepare(self):
        super().prepare()
        path = self.get_query_argument('path', None)
        if path:
            self.path = normalize_path(path)

    def get_path(self):
        if not self.path:
            raise web.HTTPError(HTTPStatus.BAD_GATEWAY)
        return self.path


class FileListHandler(FileCommonHandler):
    def get(self):
        path = self.get_path()
        if not os.path.isdir(path):
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
            return
        lst = []
        lst.append({
            'type': 'dir',
            'path': '..',
            'name': '..'
        })
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_dir() or entry.is_file():
                    entry_type = 'dir' if entry.is_dir() else 'file'
                    lst.append({
                        'type': entry_type,
                        'path': entry.path,
                        'name': entry.name
                    })
        def entry_cmp(e1, e2):
            if e1['type'] == 'dir' and e2['type'] == 'file':
                return -1
            if e1['type'] == 'file' and e2['type'] == 'dir':
                return 1
            return int(e1['name'] > e2['name'])
        lst.sort(key=functools.cmp_to_key(entry_cmp))
        self.write_json({
            'current_path': path,
            'entries': lst
        })


class ReloadHandler(FileCommonHandler):
    def initialize(self, mock):
        self.mock = mock

    async def post(self):
        path = self.get_path()
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
            return
        message = await reload_file(path, self.mock)
        self.write(message)


class FileHandler(FileCommonHandler):
    def get(self):
        path = self.get_path()
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
            return
        with open(path, encoding='utf-8') as f:
            self.write_text(f.read())

    def put(self):
        path = self.get_path()
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
            return
        content = str(self.request.body, encoding='utf-8')
        with open(path, encoding='utf-8', mode='w') as f:
            f.write(content)

    def post(self):
        path = self.get_path()
        if not os.path.isdir(path):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        file_name = self.get_query_argument('name')
        file_type = self.get_query_argument('type')
        file_path = os.path.join(path, file_name)
        if file_type == 'folder':
            os.mkdir(file_path)
        elif file_type == 'file':
            open(file_path, 'a').close()
        else:
            self.send_error(HTTPStatus.BAD_REQUEST)


def _get_tunnel(handler):
    port = handler.get_query_argument('port')
    t = tunnel.get_tunnel(port)
    if not t:
        raise web.HTTPError(HTTPStatus.NOT_FOUND, f'tunnel[{port}] not found')
    return t


def _get_connection(handler):
    t = _get_tunnel(handler)
    conn_id = handler.get_query_argument('conn_id')
    if conn_id not in t.connections:
        raise web.HTTPError(HTTPStatus.NOT_FOUND, f'connection[{conn_id}] not found in tunnel')
    return t.connections[conn_id]


class TunnelServerHandler(CommonRequestHandler):
    def get(self):
        tunnel_list = tunnel.get_tunnels()
        self.write_json([{
            'port': t.port,
            'dest_host': t.dest_host,
            'dest_port': t.dest_port,
            'status': t.status
        } for t in tunnel_list])

    async def post(self):
        action = self.get_query_argument('action')
        if action == 'start':
            t = _get_tunnel(self)
            await t.start()
            self.write_text('tunnel started')
        elif action == 'stop':
            t = _get_tunnel(self)
            await t.stop()
            self.write_text('tunnel stopped')
        else:
            raise web.HTTPError(HTTPStatus.BAD_REQUEST, f'unknown action {action}')


class TunnelConnectionHandler(CommonRequestHandler):
    def get(self):
        t = _get_tunnel(self)
        self.write_json([{
            'conn_id': c.conn_id,
            'peer_ip': c.peer_ip,
            'peer_port': c.peer_port
        } for c in t.connections.values()])

    async def post(self):
        action = self.get_query_argument('action')
        if action == 'close':
            conn = _get_connection(self)
            conn.cancel()
            self.write_text('connection closed')
        elif action == 'reset':
            conn = _get_connection(self)
            socket_nolinger(conn.local_socket)
            if conn.dest_socket:
                socket_nolinger(conn.dest_socket)
            conn.cancel()
            self.write_text('connection reset')
        else:
            raise web.HTTPError(HTTPStatus.BAD_REQUEST, f'unknown action {action}')


class LogWSHandler(websocket.WebSocketHandler):
    def initialize(self):
        self.client_id = randstr(10)
        self.queue = asyncio.Queue(100)
        self.task = asyncio.create_task(self.start())

    async def start(self):
        while True:
            log = await self.queue.get()
            self.write_message(log)

    def open(self):
        logger.debug(f'[{self.client_id}] log client connected')
        log_clients.append(self)

    def on_message(self, message):
        # ignore client message
        pass

    def on_close(self):
        logger.debug(f'[{self.client_id}] log client disconnected')
        log_clients.remove(self)
        self.task.cancel()

    def send_log(self, log):
        try:
            self.queue.put_nowait(log)
        except asyncio.QueueFull:
            logger.warn(f'[{self.client_id}] log queue full')


def get_log_clients():
    return log_clients


def setup_controller(mock, port, https, addr):
    res_dir = os.path.join(os.path.dirname(__file__), 'res')
    app = web.Application([
        (r'/', web.RedirectHandler, {'url': '/static/index.html'}),
        (r'/static/(.*)', FileWithAuthHandler, {'path': res_dir}),
        (r'/file/list', FileListHandler),
        (r'/file', FileHandler),
        (r'/file/reload', ReloadHandler, {'mock': mock}),
        (r'/ws/logs', LogWSHandler),
        (r'/tunnel', TunnelServerHandler),
        (r'/tunnel/connection', TunnelConnectionHandler)
    ])
    if https:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain('server.crt', 'server.key')
        http_server = httpserver.HTTPServer(app, ssl_options=ssl_ctx)
    else:
        http_server = httpserver.HTTPServer(app)
    http_server.listen(port, addr)