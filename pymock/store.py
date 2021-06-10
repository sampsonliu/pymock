import time
import asyncio
import random
import logging

_ARG_DEFAULT = object()
logger = logging.getLogger('store')


class StoreItem:
    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at


class Store:
    def __init__(self):
        self.store = {}
        self.expiring_delay = 300
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._expiring_task(0, 20))

    async def _expiring_task(self, delay, size):
        assert size > 0
        if delay > 0:
            await asyncio.sleep(delay)
        logger.debug('start expiring keys')
        if size >= len(self.store):
            keys = list(self.store.keys())
        else:
            keys = random.sample(self.store.keys(), size)
        count = 0
        now = time.time()
        for key in keys:
            item = self.store[key]
            if item.expires_at is not None and item.expires_at <= now:
                logger.debug('expired key: %s', key)
                count += 1
                del self.store[key]
        if count/size > 0.25:
            self.loop.create_task(self._expiring_task(0, size))
        else:
            self.loop.create_task(self._expiring_task(self.expiring_delay, size))

    def flush_all(self):
        self.store.clear()
    
    def put(self, key, value, expires=None):
        if expires is not None:
            if expires <= 0:
                return
            expires_at = time.time() + expires
        else:
            expires_at = None
        self.store[key] = StoreItem(value, expires_at=expires_at)
    
    def get(self, key, default=_ARG_DEFAULT, expires=None):
        if key in self.store:
            item = self.store[key]
            if item.expires_at > time.time():
                return item.value
        if default == _ARG_DEFAULT:
            return None
        self.put(key, default, expires)
        return default

    def expires(self, key, expires):
        if expires is not None:
            if expires <= 0:
                del self.store[key]
                return
            expires_at = time.time() + expires
        else:
            expires_at = None
        if key in self.store:
            item = self.store[key]
            item.expires_at = expires_at