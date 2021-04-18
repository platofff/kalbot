import asyncio
import json
import logging
from asyncio import Condition, AbstractEventLoop
from concurrent.futures.process import ProcessPoolExecutor
from random import randint

import aiofiles
import aioredis

from common.demotivator import Demotivator
from common.searchimages import ImgSearch
from common.tagsformatter import TagsFormatter

logger = logging.getLogger(__name__)


class Vasya:
    cacheSize = 10
    _demCache: list = []
    _d: Demotivator
    _i: ImgSearch
    _loop: AbstractEventLoop
    _pool: ProcessPoolExecutor
    _db: aioredis.commands.Redis
    cv: Condition

    @classmethod
    async def new(cls, demotivator: Demotivator,
                  img_search: ImgSearch,
                  loop: AbstractEventLoop,
                  pool: ProcessPoolExecutor,
                  redis_uri: str):
        self = Vasya()
        self._db = await aioredis.create_redis_pool(redis_uri, db=1)
        if not await self._db.exists('vasya'):
            logger.info('Loading Vasya DB to Redis...')
            async with aiofiles.open("vasya.json") as v:
                tr = self._db.multi_exec()
                for key, value in json.loads(await v.read()).items():
                    tr.sadd('vasya', json.dumps({TagsFormatter.format(key):
                                                 [TagsFormatter.format(x) for x in value]}, ensure_ascii=False))
                await tr.execute()
            logger.info('Successfully loaded Vasya cache to Redis!')

        self._d = demotivator
        self._i = img_search
        self._loop = loop
        self._pool = pool
        self.cv = Condition()
        return self

    async def run(self) -> None:
        while True:
            if len(self._demCache) < self.cacheSize:
                await self._getDemotivator()
            await asyncio.sleep(1)

    async def _getDemotivator(self) -> None:
        async def get_links():
            msg = json.loads(await self._db.srandmember('vasya'))
            msg0 = list(msg.keys())[0]
            msg1 = ' '.join(list(msg.values())[0])
            query = msg0
            links = await self._loop.run_in_executor(self._pool, self._i.search, query)
            return msg0, msg1, query, links

        while True:
            msg0, msg1, query, links = await get_links()
            if links:
                break
        link = links[randint(0, len(links) - 1)]
        while True:
            dem = await self._loop.run_in_executor(self._pool,
                                                   self._d.create,
                                                   link,
                                                   msg0,
                                                   msg1.splitlines(),
                                                   f'demotivator{len(self._demCache)}.png')
            if dem:
                break
            else:
                try:
                    links.pop(links.index(link))
                    link = links[randint(0, len(links) - 1)]
                except ValueError:
                    while True:
                        msg0, msg1, query, links = await get_links()
                        if links:
                            break
                continue
        self._demCache.append(dem)
        async with self.cv:
            self.cv.notify()
        logger.debug(f'There are {len(self._demCache)} of {self.cacheSize} images in demotivators cache now.')

    async def getDemotivator(self) -> str:
        async with self.cv:
            while not self._demCache:
                await self.cv.wait()
            dem = self._demCache.pop(-1)
            logger.debug(f'There are {len(self._demCache)} of {self.cacheSize} images in demotivators cache now.')
            return dem
