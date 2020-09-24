import json
from random import randint, choice
from threading import Thread, Condition
from time import sleep
from urllib.error import HTTPError, URLError

from PIL import UnidentifiedImageError

from images.demotivator import Demotivator
from images.searchimages import ImgSearch


class Vasya(Thread):
    cachesize = 10
    _demCache = []
    _d: Demotivator
    _i: ImgSearch

    def __init__(self, demotivator: Demotivator, imgSearch: ImgSearch):
        Thread.__init__(self)
        with open("vasya.json") as v:
            self._v = json.load(v)
        self.running = True
        self._d = demotivator
        self._i = imgSearch
        self.cv = Condition()

    def run(self) -> None:
        while self.running:
            if len(self._demCache) < self.cachesize:
                for i in range(10 - len(self._demCache)):
                    self._getDemotivator()
            sleep(1)

    def _getDemotivator(self) -> None:
        links = []
        msg0: str
        msg1: str
        while not links:
            msg0, msg1 = choice(list(self._v.items()))
            msg1 = ' '.join(msg1)
            query = msg0
            links = self._i.fetch(query)
        link = links[randint(0, len(links) - 1)]
        while True:
            try:
                dem = self._d.create(
                    link,
                    msg0,
                    msg1,
                    f'demotivator{len(self._demCache)}.png'
                )
                break
            except (UnidentifiedImageError, HTTPError, URLError):
                links.pop(links.index(link))
                link = links[randint(0, len(links) - 1)]
                continue
        self._demCache.append(dem)
        with self.cv:
            self.cv.notify()

    def getDemotivator(self) -> str:
        with self.cv:
            while not self._demCache:
                self.cv.wait()
            return self._demCache.pop(-1)
