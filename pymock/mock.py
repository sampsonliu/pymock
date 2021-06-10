import asyncio
import os
import logging
import socket
import struct
import http.client
from datetime import datetime
from tornado import ioloop, web, httputil, httpserver, httpclient

from .simple_httpclient import SimpleAsyncHTTPClient
from . import utils
from .store import Store

logger = logging.getLogger('pymock')
httpclient.AsyncHTTPClient.configure(SimpleAsyncHTTPClient)
store = Store()


class MockConnectionDelegate(httputil.HTTPServerConnectionDelegate):
    def __init__(self):
        self.processor = None

    def start_request(self, server_conn, request_conn):
        return MockMessageDelegate(server_conn, request_conn, self.processor)

    def set_processor(self, processor):
        self.processor = processor


class MockMessageDelegate(httputil.HTTPMessageDelegate):
    _ARG_DEFAULT = object()

    def __init__(self, server_conn, request_conn, processor):
        self.server_conn = server_conn
        self.request_conn = request_conn
        self._processor = processor
        self._chunk_queue = asyncio.Queue(100)
        self._header_written = False
        self._body_written = False
        self._socket_closed = False
        self._input_closed = False
        self._task = None
        self._body_parsed = False
        self._recording = False
        self.utils = utils
        self.logger = logger
        self.request_id = utils.randstr(8)
        self.request = None
        self.resp_headers = httputil.HTTPHeaders()
        self.resp_status = 200
        self.resp_reason = 'OK'
        self.resp_body = None
        self.store = store

    # override
    def headers_received(self, start_line, headers):
        logger.info(f'[{self.request_id}] REQUEST {start_line.method} {start_line.path}')
        self.request = httputil.HTTPServerRequest(
            connection=self.request_conn,
            server_connection=self.server_conn,
            start_line=start_line, headers=headers)
        self._task = asyncio.create_task(self._process(self.request))
        self._task.add_done_callback(lambda _: asyncio.create_task(self._request_done()))

    # override
    async def data_received(self, chunk):
        await self._chunk_queue.put(chunk)

    # override
    def finish(self):
        logger.debug(f'[{self.request_id}] request finished')
        if self._task:
            asyncio.create_task(self._chunk_queue.put(None))

    # override
    def on_connection_close(self):
        logger.debug(f'[{self.request_id}] connection closed')
        if self._task:
            self._task.cancel()
            asyncio.create_task(self._chunk_queue.put(None))

    async def _request_done(self):
        try:
            result = self._task.result()
            logger.debug(f'[{self.request_id}] request completed with result: {result}')
        except Exception as e:
            logger.exception(f'[{self.request_id}] request completed with error')
        finally:
            dropped = 0
            while not self._input_closed:
                chunk = await self._chunk_queue.get()
                if chunk is None:
                    self._input_closed = True
                    break
                dropped += 1
            if dropped > 0:
                dropped_msg = f'dropped {dropped} {"chunk" if dropped == 1 else "chunks"}'
                logger.debug(f'[{self.request_id}] {dropped_msg}')

    async def request_body(self):
        if self._input_closed:
            return self.request.body
        body = None
        while True:
            chunk = await self._chunk_queue.get()
            if chunk is None:
                self._input_closed = True
                break
            if body is None:
                body = chunk
            else:
                body += chunk
        self.request.body = body
        return body

    async def request_chunk(self):
        if self._input_closed:
            raise IOError()
        chunk = await self._chunk_queue.get()
        if chunk is None:
            self._input_closed = True
        return chunk

    def record(self):
        self._recording = True

    def _get_argument(self, source, name, default):
        if name in source:
            value = source[name][-1]
            return value.decode('utf-8')
        elif default == self._ARG_DEFAULT:
            raise web.MissingArgumentError(name)
        else:
            return default

    def get_query_argument(self, name, default=_ARG_DEFAULT):
        return self._get_argument(self.request.query_arguments, name, default)

    async def get_body_argument(self, name, default=_ARG_DEFAULT):
        if not self._body_parsed:
            await self.request_body()
            self.request._parse_body()
            self._body_parsed = True
        return self._get_argument(self.request.body_arguments, name, default)

    def set_header(self, name, value):
        self.resp_headers[name] = value

    def add_header(self, name, value):
        self.resp_headers.add(name, value)

    def set_status(self, code):
        self.resp_status = code
        self.resp_reason = http.client.responses[code]
    
    def set_body(self, body):
        if isinstance(body, str):
            self.resp_body = bytes(body, 'utf-8')
        elif isinstance(body, bytes):
            self.resp_body = body
        else:
            raise ValueError('unknown body type')
    
    async def write_header(self):
        if not self._header_written:
            if self._socket_closed:
                logger.info(f'[{self.request_id}] SOCKET CLOSED')
                return
            start_line = httputil.ResponseStartLine('', self.resp_status, self.resp_reason)
            if self.resp_body is not None:
                assert isinstance(self.resp_body, bytes)
                self.resp_headers['Content-Length'] = str(len(self.resp_body))
            else:
                self.resp_headers['Content-Length'] = '0'
            await self.request_conn.write_headers(start_line, self.resp_headers)
            self._header_written = True
            logger.info(f'[{self.request_id}] RESPONSE {start_line.code} {start_line.reason}')

    async def write_body(self):
        if not self._body_written and not self._socket_closed:
            if self.resp_body is not None:
                await self.request_conn.write(self.resp_body)
            self._body_written = True

    async def flush(self):
        await self.write_header()
        await self.write_body()
        self.request_conn.finish()

    async def close_socket(self, nolinger=False):
        if not self._socket_closed:
            self._socket_closed = True
            if not self.server_conn.stream.closed():
                s = self.server_conn.stream.socket
                if nolinger:
                    utils.socket_nolinger(s)
                await self.server_conn.close()

    def _remove_encoding(self, headers):
        if 'Transfer-Encoding' in headers:
            del headers['Transfer-Encoding']
        if 'Content-Encoding' in headers:
            del headers['Content-Encoding']

    async def forward(self, host, port=80, is_https=None, streaming_request=False, streaming_response=False):
        client = httpclient.AsyncHTTPClient()
        if is_https is None:
            is_https = port == 443
        port_str = '' if (is_https and port == 443 or not is_https and port == 80) else (':' + str(port))
        url = ('https' if is_https else 'http') + '://' + host + port_str + self.request.uri
        
        headers = httputil.HTTPHeaders(self.request.headers)
        self._remove_encoding(headers)
        headers['Host'] = host + port_str
        
        if streaming_request:
            body = None
            async def body_producer(write_fn):
                while True:
                    chunk = await self.request_chunk()
                    if chunk is None:
                        return
                    await write_fn(chunk)
        else:
            body = await self.request_body()
            if body and 'Content-Length' not in headers:
                headers['Content-Length'] = str(len(body))
            body_producer=None
        
        async def header_callback(start_line, headers):
            self.set_status(start_line.code)
            self.resp_headers = httputil.HTTPHeaders(headers)
            self._remove_encoding(self.resp_headers)
            if streaming_response:
                await self.request_conn.write_headers(start_line, self.resp_headers)
                logger.info(f'[{self.request_id}] RESPONSE {start_line.code} {start_line.reason}')
                self._header_written = True
        
        async def streaming_callback(chunk):
            if streaming_response:
                await self.request_conn.write(chunk)
            else:
                if self.resp_body is None:
                    self.resp_body = chunk
                else:
                    self.resp_body += chunk

        request = httpclient.HTTPRequest(
            url=url,
            method=self.request.method,
            headers=headers,
            body=body,
            body_producer=body_producer,
            header_callback=header_callback,
            streaming_callback=streaming_callback,
            follow_redirects=False
        )
        logger.info(f'[{self.request_id}] FORWARD TO {url}')
        await client.fetch(request, raise_error=False)

    async def _process(self, request):
        try:
            if self._processor is None:
                self.set_status(404)
            else:
                await self._processor(self)
        except web.HTTPError as e:
            self.set_status(e.status_code)
            if e.log_message:
                self.set_body(e.log_message)
        except Exception as e:
            logger.exception(f'[{self.request_id}] EXCEPTION')
            self.set_status(500)
            self.set_body(str(e))
        finally:
            if self._recording:
                time_str = datetime.now().strftime('%H%M%S%f')
                filename = f'{time_str}-{utils.safe_filename(self.request.path)}.txt'
                with open(f'recordings/{filename}', 'wb') as out:
                    out.write(b'===== REQUEST =====\n')
                    out.write(f'{self.request.method} {self.request.uri}\n'.encode('ascii'))
                    for name, value in self.request.headers.get_all():
                        out.write(f'{name}: {value}\n'.encode('ascii'))
                    out.write(b'\n')
                    body = await self.request_body()
                    if body is not None:
                        out.write(body)
                    out.write(b'\n===== RESPONSE =====\n')
                    out.write(f'{self.resp_status} {self.resp_reason}\n'.encode('ascii'))
                    for name, value in self.resp_headers.get_all():
                        out.write(f'{name}: {value}\n'.encode('ascii'))
                    out.write(b'\n')
                    if self.resp_body is not None:
                        out.write(self.resp_body)
            await self.flush()


def setup_wslogs():
    from pymock.controller import get_log_clients
    from pymock.wshandler import WebsocketHandler
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler = WebsocketHandler(get_log_clients)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def setup_mock(port, addr):
    mock = MockConnectionDelegate()
    server = httpserver.HTTPServer(mock)
    server.listen(port, addr)
    return mock
