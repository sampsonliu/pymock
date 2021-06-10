from concurrent.futures import ThreadPoolExecutor
from tornado import ioloop
import os
from . import mock, tunnel, controller
from .utils import init_logging, set_verbose
from .config import load_config
import argparse
import logging
import sys
import asyncio
import signal

init_logging()
logger = logging.getLogger('pymock.main')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose logging')
    parser.add_argument('-mp', type=int, default=8080, help='mock port')
    parser.add_argument('-cp', type=int, default=80, help='controller port')
    parser.add_argument('-wd', help='working directory')
    parser.add_argument('-p', help='password')
    parser.add_argument('-addr', default='0.0.0.0', help='bind ip address')
    parser.add_argument('-https', action='store_true', help='use https for webui')
    opts = parser.parse_args()
    if opts.verbose:
        set_verbose()
    if opts.wd:
        os.chdir(opts.wd)
    if opts.https and (not os.path.isfile('server.crt') or not os.path.isfile('server.key')):
        print('file {server.crt, server.key} is required in https mode', file=sys.stderr)
        exit(1)
    if not os.path.isfile('config.json'):
        with open('config.json', 'w', encoding='ascii') as out:
            out.write('{}')
    if not os.path.isdir('recordings'):
        os.mkdir('recordings')
    mock_port = opts.mp
    controller_port = opts.cp
    controller.server_password = opts.p

    mocker = mock.setup_mock(mock_port, opts.addr)
    mock_processor, tunnel_list = load_config()
    mocker.set_processor(mock_processor)
    tunnel.setup_tunnel(tunnel_list)

    controller.setup_controller(mocker, controller_port, opts.https, opts.addr)
    mock.setup_wslogs()

    # setup event loop
    _executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tornado")
    _ioloop = ioloop.IOLoop.current()
    _ioloop.set_default_executor(_executor)
    loop = asyncio.get_event_loop()
    # windows select() is not interruptible
    if os.name == 'nt':
        period_check = ioloop.PeriodicCallback(lambda: None, 1000)
        period_check.start()
    else:
        loop.add_signal_handler(signal.SIGTERM, lambda: _ioloop.stop())
    try:
        logger.info(f'starting server, mock_port={mock_port}, controller_port={controller_port}')
        _ioloop.start()
    except KeyboardInterrupt as e:
        pass
    logger.info(f'server stopped')


if __name__ == '__main__':
    main()
