import asyncio
import logging
from . import utils

logger = logging.getLogger('pymock.tunnel')
tunnel_map = {}
processor = None


class ControllerBase:
    def __init__(self, conn):
        self.conn = conn
        self.logger = logger
        self.conn_id = self.conn.conn_id

    def on_connected(self):
        pass

    async def on_output(self, data):
        pass

    async def on_input(self, data):
        pass


class Connection:
    def __init__(self, conn_id, local_reader, local_writer, tunnel):
        self.conn_id = conn_id
        self.local_reader = local_reader
        self.local_writer = local_writer
        self.tunnel = tunnel
        peer_info = local_writer.get_extra_info('peername')
        self.peer_ip, self.peer_port = peer_info[0], peer_info[1]
        self.desc = f'{self.peer_ip}:{self.peer_port} => {self.tunnel.dest_host}:{self.tunnel.dest_port}'
        self.local_socket = local_writer.get_extra_info('socket')
        self.dest_reader = self.dest_writer = self.dest_socket = self.conn_fut = None
        self.cancelled = False
        self.controller = tunnel.controller_cls(self)
        self.utils = utils

    async def start(self):
        dest_host = self.tunnel.dest_host
        dest_port = self.tunnel.dest_port
        self.dest_reader, self.dest_writer = await asyncio.open_connection(dest_host, dest_port)
        self.dest_socket = self.dest_writer.get_extra_info('socket')
        logger.info(f'[{self.conn_id}] tunnel connected {self.desc}')
        self.controller.on_connected()
        input_co = self.proxy_in()
        output_co = self.proxy_out()
        self.conn_fut = asyncio.gather(input_co, output_co)
        try:
            await self.conn_fut
            logger.info(f'[{self.conn_id}] tunnel closed {self.desc}')
        except:
            if self.cancelled:
                logger.info(f'[{self.conn_id}] tunnel cancelled {self.desc}')
            else:
                logger.exception(f'[{self.conn_id}] tunnel error {self.desc}')
                # cancel the remain task
                self.conn_fut.cancel()
        finally:
            self.tunnel.on_disconnect(self)

    def cancel(self):
        if self.conn_fut:
            self.cancelled = True
            self.conn_fut.cancel()

    async def proxy_out(self):
        try:
            while True:
                data = await self.local_reader.read(1024)
                if data:
                    await self.controller.on_output(data)
                    self.dest_writer.write(data)
                    await self.dest_writer.drain()
                else:
                    self.dest_writer.write_eof()
                    return True
        except:
            self.dest_writer.close()
            raise

    async def proxy_in(self):
        try:
            while True:
                data = await self.dest_reader.read(1024)
                if data:
                    await self.controller.on_input(data)
                    self.local_writer.write(data)
                    await self.local_writer.drain()
                else:
                    self.local_writer.write_eof()
                    return True
        except:
            self.local_writer.close()
            raise


class Tunnel:
    def __init__(self, port, dest_host, dest_port, controller_cls):
        self.port = port
        self.dest_host = dest_host
        self.dest_port = dest_port
        self.desc = f'{self.port} => {dest_host}:{dest_port}'
        if controller_cls:
            self.controller_cls = controller_cls
        else:
            self.controller_cls = ControllerBase
        self.connections = {}
        self.server = None
        self.status = 'stopped'
        
    async def start(self):
        logger.info(f'starting tunnel server {self.desc}')
        if self.status != 'stopped':
            return
        self.status = 'starting'
        self.started = True
        self.server = await asyncio.start_server(self.on_connect, port=self.port)
        self.status = 'started'

    async def on_connect(self, local_reader, local_writer):
        while True:
            conn_id = utils.randstr(8)
            if conn_id not in self.connections:
                break
        conn = Connection(conn_id, local_reader, local_writer, self)
        self.connections[conn_id] = conn
        await conn.start()

    def on_disconnect(self, conn):
        del self.connections[conn.conn_id]

    async def stop(self):
        logger.info(f'stopping tunnel server {self.desc}')
        if self.status != 'started':
            return
        self.status = 'stopping'
        self.started = False
        self.server.close()
        await self.server.wait_closed()
        for conn in self.connections.values():
            conn.cancel()
        self.status = 'stopped'


def get_tunnels():
    return tunnel_map.values()


def get_tunnel(port):
    return utils.dict_get(tunnel_map, port, None)


async def start_tunnel(tunnel):
    port = tunnel.port
    if port in tunnel_map:
        t = tunnel_map[port]
        await t.stop()
    tunnel_map[port] = tunnel
    await tunnel.start()


async def reload_tunnel(tunnel_list):
    for _, tunnel in tunnel_map.items():
        await tunnel.stop()
    tunnel_map.clear()
    for tunnel in tunnel_list:
        await start_tunnel(tunnel)


def setup_tunnel(tunnel_list):
    for tunnel in tunnel_list:
        loop = asyncio.get_event_loop()
        tunnel_task = loop.create_task(start_tunnel(tunnel))
        def done(fut):
            try:
                fut.result()
            except:
                logger.exception('error starting tunnel server')
        tunnel_task.add_done_callback(done)
