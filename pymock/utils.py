import logging
import sys
import os
import string
import random
import socket
import struct

_ARG_DEFAULT = object()
safe_chars = '_-.' + string.ascii_letters + string.digits

def init_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def set_verbose():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)


def randstr(length):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def dict_get(source, key, default=_ARG_DEFAULT):
    if key in source:
        return source[key]
    elif default != _ARG_DEFAULT:
        source[key] = default
        return default
    else:
        raise KeyError(key)


def safe_filename(filename):
    return ''.join(c if c in safe_chars else '_' for c in filename)


def normalize_path(path):
    abspath = os.path.abspath(path)
    cwd = os.getcwd()
    if os.path.commonpath([abspath, cwd]) != cwd:
        return '.'
    else:
        return os.path.relpath(abspath)


def socket_nolinger(s):
    if os.name == 'nt':
        opt_value = struct.pack('hh', 1, 0)
    else:
        opt_value = struct.pack('ii', 1, 0)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, opt_value)