import logging
import re
import json
import os.path
from .utils import normalize_path
from .tunnel import Tunnel, ControllerBase, reload_tunnel

logger = logging.getLogger('pymock.config')
config_file = 'config.json'
rule_list = []
controller_list = []


def _load_item(file, var_name, scope={}):
    if not os.path.isfile(file):
        raise ValueError(f'{file} is not a file')
    with open(file, encoding='utf-8') as f:
        code = f.read()
    exec(code, scope)
    if var_name not in scope:
        raise ValueError(f'no {var_name} defined in {file}')
    logger.debug(f'{file}:{var_name} loaded')
    return scope[var_name]


def load_mock_processor(file):
    processor = _load_item(file, 'processor')
    if not callable(processor):
        raise ValueError('processor should be callable')
    return processor


def load_tunnel_controller(file):
    controller = _load_item(file, 'Controller', scope={'ControllerBase': ControllerBase})
    if not issubclass(controller, ControllerBase):
        raise ValueError(f'Controller should be subclass of ControllerBase')
    return controller


class Rule:
    def __init__(self, prefix, processor, file_path, strip):
        self.prefix = prefix
        self.strip = strip
        self.processor = processor
        self.file_path = file_path


async def reload_file(file, mock):
    if file == config_file:
        generator, tunnel_list = load_config()
        mock.set_processor(generator)
        await reload_tunnel(tunnel_list)
        return 'config file reloaded'
    else:
        for item in rule_list:
            if item.file_path == file:
                processor = load_mock_processor(file)
                item.processor = processor
                return 'processor file reloaded'
        for item in controller_list:
            if item['file_path'] == file:
                controller_cls = load_tunnel_controller(file)
                item['tunnel'].controller_cls = controller_cls
                return 'controller file reloaded'
    return 'unregistered file, ignore'


def generate_mock_processor(config):
    if 'mock' in config:
        rule_list.clear()
        for idx, item in enumerate(config['mock']):
            if 'prefix' not in item:
                raise ValueError(f'prefix required for rules[{idx}]')
            if 'file' not in item:
                raise ValueError(f'file required for rules[{idx}]')
            prefix = item['prefix']
            file_path = normalize_path(item['file'])
            processor = load_mock_processor(file_path)
            strip = item['strip'] if 'strip' in item else True
            rule = Rule(prefix, processor, file_path, strip)
            rule_list.append(rule)
    async def mock_processor(ctx):
        for rule in rule_list:
            if ctx.request.path.startswith(rule.prefix):
                logger.debug('found matched processor: ' + rule.file_path)
                if rule.strip:
                    prefix_len = len(rule.prefix)
                    ctx.request.path = ctx.request.path[prefix_len:]
                    ctx.request.uri = ctx.request.uri[prefix_len:]
                await rule.processor(ctx)
                return
        ctx.logger.error(f'no processor found for {ctx.request.path}')
        ctx.set_status(404)
    return mock_processor


def load_tunnels(config):
    tunnel_list = []
    if 'tunnel' in config:
        controller_list.clear()
        tunnel_cfg = config['tunnel']
        if 'mappings' in tunnel_cfg:
            for mapping in tunnel_cfg['mappings']:
                if 'port' not in mapping or 'dest_host' not in mapping or 'dest_port' not in mapping:
                    logger.error('port|dest_host|dest_port is required for tunnel mappings')
                    exit(1)
                if 'controller' in mapping:
                    controller_file = normalize_path(mapping['controller'])
                    controller_cls = load_tunnel_controller(controller_file)
                else:
                    controller_file = None
                    controller_cls = None
                tunnel = Tunnel(mapping['port'], mapping['dest_host'], mapping['dest_port'], controller_cls)
                tunnel_list.append(tunnel)
                if controller_file:
                    controller_list.append({
                        'tunnel': tunnel,
                        'file_path': controller_file
                    })
    return tunnel_list


def load_config():
    with open(config_file, encoding='utf-8') as f:
        config = json.loads(f.read())
    return generate_mock_processor(config), load_tunnels(config)