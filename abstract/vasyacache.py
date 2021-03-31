import asyncio
import json
import logging
from asyncio import Condition
from concurrent.futures.process import ProcessPoolExecutor
from random import randint, choice

from abstract.demotivator import Demotivator
from abstract.searchimages import ImgSearch

logger = logging.getLogger(__name__)


class Vasya:
    cacheSize = 10
    _demCache: list = []

    def __init__(self, demotivator: Demotivator,
                 img_search: ImgSearch,
                 loop: asyncio.BaseEventLoop,
                 pool: ProcessPoolExecutor):
        with open("vasya.json") as v:
            self._v = json.load(v)
        self.running = True
        self._d = demotivator
        self._i = img_search
        self._loop = loop
        self._pool = pool
        self.cv = Condition()

    async def run(self) -> None:
        while self.running:
            if len(self._demCache) < self.cacheSize:
                await self._getDemotivator()
            await asyncio.sleep(1)

    async def _getDemotivator(self) -> None:
        async def get_links():
            msg0, msg1 = choice(list(self._v.items()))
            msg1 = ' '.join(msg1)
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
                links.pop(links.index(link))
                try:
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
