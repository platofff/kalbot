import re
from os import environ, remove
from typing import Callable, Awaitable, Any

import yaml
import logging

from vkwave.api import Token, BotSyncSingleToken, API
from vkwave.api.methods._error import APIError
from vkwave.bots import TokenStorage, GroupId, Dispatcher, BotLongpollExtension, PhotoUploader, DefaultRouter, \
    EventTypeFilter, BotEvent, BaseEvent
from vkwave.bots.core import BaseFilter
from vkwave.bots.core.dispatching.filters.base import FilterResult
from vkwave.client import AIOHTTPClient
from vkwave.longpoll import BotLongpollData, BotLongpoll
from vkwave.types.bot_events import BotEventType
from sys import path

path.append("...")
from abstract.bot import Bot as AbstractBot

logger = logging.getLogger("VK-Wave")


class Bot(AbstractBot):
    _gid: int
    _admins: list
    _apiSession: API
    _uploader: PhotoUploader
    _lpExtension: BotLongpollExtension
    _dp: Dispatcher
    _apiMethods = {}

    async def _sendImagesFromURLs(self, peerId: int, urls: list, userId=None) -> None:
        attachment = await self._uploader.get_attachments_from_links(links=urls, peer_id=userId)
        await self._apiSession.get_context().messages.send(
            peer_id=peerId, attachment=attachment, random_id=0
        )

    async def _sendImagesFromFiles(self, peerId: int, files: list, userId=None) -> None:
        attachment = await self._uploader.get_attachments_from_paths(file_paths=files, peer_id=userId)
        await self._apiSession.get_context().messages.send(
            peer_id=peerId, attachment=attachment, random_id=0
        )
        for f in files:
            remove(f)

    async def _sendText(self, userId: int, text: str):
        await self._apiSession.get_context().messages.send(
            peer_id=userId, message=text, random_id=0
        )

    def __init__(self):
        AbstractBot.__init__(self)
        if not ('VK_BOT_TOKEN' in environ):
            with open('vkapi.yaml') as c:
                config = yaml.safe_load(c)
                botToken = Token(config["bot_token"])
                self._gid = config["group_id"]
                self._admins = config["admin_ids"]
        else:
            botToken = Token(environ['VK_BOT_TOKEN'])
            self._gid = int(environ['VK_BOT_GID'])
            self._admins = [int(x) for x in environ["VK_BOT_ADMINS"].split(",")]

        client = AIOHTTPClient()
        token = BotSyncSingleToken(botToken)
        self._apiSession = API(token, client)
        api = self._apiSession.get_context()
        lpData = BotLongpollData(self._gid)
        longpoll = BotLongpoll(api, lpData)
        token_storage = TokenStorage[GroupId]()
        self._dp = Dispatcher(self._apiSession, token_storage)
        self._lpExtension = BotLongpollExtension(self._dp, longpoll)
        self._uploader = PhotoUploader(self._apiSession.get_context())
        self._router = DefaultRouter()
        self._dp.add_router(self._router)
        for methodName in dir(self):
            if methodName.startswith('_send'):
                self._apiMethods.update({methodName[1:]: getattr(self, methodName)})

    async def _regHandlers(self):
        for i in dir(self):
            try:
                if not ('__' in i or '_Handler' in i) and getattr(self, i).__weakref__.__objclass__ == self._Handler:
                    await self._regHandler(getattr(self, i))
            except AttributeError:
                pass

    @classmethod
    async def create(cls):
        self = Bot()
        await self._regHandlers()

        await self._dp.cache_potential_tokens()
        await self._lpExtension.start()
        return self

    class _Callback:
        def __init__(self, func: Callable[[int, str, list or None], Awaitable[list]], imageType: type,
                     apiMethods: dict):
            self._func = func
            self._imageType = imageType
            self._apiMethods = apiMethods

        async def execute(self, event: BaseEvent) -> None:
            attachedPhotos = []
            msg = event.object.object.message.text
            if event.object.object.message.from_id != event.object.object.message.peer_id:
                userId = event.object.object.message.from_id
                msg = msg[1:]
            else:
                userId = None

            for attachment in event.object.object.message.attachments:
                if attachment.photo:
                    attachedPhotos.append(attachment.photo.sizes[-1].url)

            fwd = []
            for x in [event.object.object.message.reply_message] + event.object.object.message.fwd_messages:
                if x:
                    fwd.append(x.text)
                    for attachment in x.attachments:
                        if attachment.photo:
                            attachedPhotos.append(attachment.photo.sizes[-1].url)

            if fwd:
                fwd = '\n'.join(fwd)
                if ' ' in msg:
                    msg = f'{msg}\n{fwd}'
                else:
                    msg = f'{msg} {fwd}'
            try:
                msg = re.sub(r'\[.*\|.*\]', re.findall(r'\|.*\]', msg)[0][1:-1], msg)
            except IndexError:
                pass

            r = await self._func(event.object.object.message.from_id,
                                 msg, attachedPhotos)

            for msg in r:
                if type(msg) is self._imageType:
                    try:
                        if msg.url:
                            await self._apiMethods['sendImagesFromURLs'](event.object.object.message.peer_id,
                                                                         [msg.url], userId)
                        elif msg.filepath:
                            await self._apiMethods['sendImagesFromFiles'](event.object.object.message.peer_id,
                                                                          [msg.filepath], userId)
                    except APIError:
                        await self._apiMethods['sendText'](event.object.object.message.peer_id,
                                    ["Начни переписку со мной, чтобы оформлять картинки. И желательно подпишись :)"])
                        break
                elif type(msg) is str:
                    await self._apiMethods['sendText'](event.object.object.message.peer_id, [msg])

    async def _regHandler(self, h: type) -> None:
        eventTypeFilter = EventTypeFilter(BotEventType.MESSAGE_NEW)
        rateCounter = self._rateLimit.ratecounter

        class TextFilter(BaseFilter):
            def __init__(self, h):
                super().__init__()
                self.h = h

            async def check(self, event: BotEvent) -> FilterResult:
                if not await rateCounter(event.object.object.message.from_id, event.object.object.message.id):
                    logger.debug(f"Oh shit, I'm sorry: {event.object.object.message.from_id} is banned.")
                    return FilterResult(False)
                msg = event.object.object.message.text.lower()
                if event.object.object.message.from_id != event.object.object.message.peer_id:
                    msg = msg[1:]
                return FilterResult(await self.h.filter(msg))

        textFilter = TextFilter(h)
        handler = self._router.registrar.new()
        handler.filters = [eventTypeFilter, textFilter]
        hI = h(self._rateLimit.ratecounter, self._imgSearch)
        h = self._Callback(hI.run, self._Handler.Image, self._apiMethods)
        handler.callback = h
        ready = handler.ready()
        self._router.registrar.register(ready)
