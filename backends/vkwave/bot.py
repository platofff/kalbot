import inspect
import re
from inspect import signature
from os import environ, remove
from typing import Callable, Awaitable

import pymysql
import yaml
import logging

from vkwave.api import Token, BotSyncSingleToken, API
from vkwave.api.methods._error import APIError
from vkwave.bots import TokenStorage, GroupId, Dispatcher, BotLongpollExtension, PhotoUploader, DefaultRouter, \
    EventTypeFilter, BotEvent, BaseEvent, DocUploader
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
    _photoUploader: PhotoUploader
    _docUploader: DocUploader
    _lpExtension: BotLongpollExtension
    _dp: Dispatcher
    _apiMethods = {}

    async def _APIsendImagesFromURLs(self, peerId: int, urls: list, userId=None) -> None:
        attachment = await self._photoUploader.get_attachments_from_links(links=urls, peer_id=userId)
        await self._apiSession.get_context().messages.send(
            peer_id=peerId, attachment=attachment, random_id=0
        )

    async def _APIsendImagesFromFiles(self, peerId: int, files: list, userId=None) -> None:
        attachment = await self._photoUploader.get_attachments_from_paths(file_paths=files, peer_id=userId)
        await self._apiSession.get_context().messages.send(
            peer_id=peerId, attachment=attachment, random_id=0
        )
        for f in files:
            remove(f)

    async def _APIsendText(self, userId: int, text: str) -> None:
        await self._apiSession.get_context().messages.send(
            peer_id=userId, message=text, random_id=0
        )

    async def _APIsendDocs(self, userId: int, files: list) -> None:
        attachment = await self._docUploader.get_attachments_from_paths(file_paths=files, peer_id=userId)
        await self._apiSession.get_context().messages.send(
            peer_id=userId, attachment=attachment, random_id=0
        )

    async def _APIgetUsers(self, userIds: list) -> dict:
        return await self._apiSession.get_context().users.get(user_ids=userIds)

    async def _APIgetGroups(self, groupIds: list) -> dict:
        return await self._apiSession.get_context().groups.get_by_id(group_ids=groupIds)

    async def _APIgetMessagesById(self, messagesIds: list) -> list:
        return (await self._apiSession.get_context().messages.get_by_id(message_ids=messagesIds)).response.items

    def __init__(self, dbConnection: pymysql.connections.Connection):
        AbstractBot.__init__(self, dbConnection)
        if not ('VK_BOT_TOKEN' in environ):
            with open('vkapi.yaml') as c:
                config = yaml.safe_load(c)
                botToken = Token(config["bot_token"])
                self._gid = config["group_id"]
        else:
            botToken = Token(environ['VK_BOT_TOKEN'])
            self._gid = int(environ['VK_BOT_GID'])

        client = AIOHTTPClient()
        token = BotSyncSingleToken(botToken)
        self._apiSession = API(token, client)
        api = self._apiSession.get_context()
        lpData = BotLongpollData(self._gid)
        longpoll = BotLongpoll(api, lpData)
        tokenStorage = TokenStorage[GroupId]()
        self._dp = Dispatcher(self._apiSession, tokenStorage)
        self._lpExtension = BotLongpollExtension(self._dp, longpoll)
        self._photoUploader = PhotoUploader(api)
        self._docUploader = DocUploader(api)
        self._router = DefaultRouter()
        self._dp.add_router(self._router)
        for methodName in dir(self):
            if methodName.startswith('_API'):
                self._apiMethods.update({methodName[4:]: getattr(self, methodName)})

    async def _regHandlers(self):
        for i in dir(self):
            try:
                if not ('__' in i or '_Handler' in i) and getattr(self, i).__weakref__.__objclass__ == self._Handler:
                    await self._regHandler(getattr(self, i))
            except AttributeError:
                pass

    @classmethod
    async def create(cls, dbConnection: pymysql.connections.Connection):
        self = Bot(dbConnection)
        await self._regHandlers()

        await self._dp.cache_potential_tokens()
        await self._lpExtension.start()
        return self

    class _Callback:
        _func: Callable[[int, str, list or None], Awaitable[list]]
        _imageType: type
        _docType: type
        _apiMethods: dict
        _rateCounter: Callable[[int], Awaitable[bool]]

        class TagsFormatter:
            def _get(self, match: re.Match) -> str:
                return re.sub(r'\[.*\|', '', match.group(0))[:-1]

            def format(self, msg: str) -> str:
                return re.sub(r'\[.*?\|.*?\]', self._get, msg)

        _tagsFormatter: TagsFormatter

        def __init__(self, func: Callable[[int, str, list or None], Awaitable[list]], imageType: type,
                     apiMethods: dict, rateCounter: Callable[[int], Awaitable[bool]], docType: type):
            self._func = func
            self._imageType = imageType
            self._docType = docType
            self._apiMethods = apiMethods
            self._rateCounter = rateCounter
            self._tagsFormatter = self.TagsFormatter()
            self._funcParams = signature(self._func).parameters

        async def execute(self, event: BaseEvent) -> None:
            vkMessage = event.object.object.message
            if vkMessage.is_cropped:
                if vkMessage.from_id != vkMessage.peer_id:
                    await self._apiMethods['sendText'](vkMessage.peer_id,
                                                       ['Твое сообщение слишком большое, попробуй написать мне в ЛС!'])
                    return None
                vkMessage = (await self._apiMethods['getMessagesById']([vkMessage.id]))[0]
            if not await self._rateCounter(vkMessage.from_id):
                logger.debug(f"Oh shit, I'm sorry: {vkMessage.from_id} is banned.")
                return None
            msg = vkMessage.text
            if vkMessage.from_id != vkMessage.peer_id:
                userId = vkMessage.from_id
                msg = msg[1:]
            else:
                userId = None
            attachedPhotos = []
            if 'attachedPhotos' in self._funcParams:
                for attachment in vkMessage.attachments:
                    if attachment.photo:
                        attachedPhotos.append(attachment.photo.sizes[-1].url)

            fwd = []
            fwdNames = []

            def unpackFwd(msgs):
                for x in msgs:
                    if x:
                        if x.text:
                            fwd.append(x.text)
                            fwdNames.append(x.from_id)
                        if x.fwd_messages:
                            unpackFwd(x.fwd_messages)
                        if 'attachedPhotos' in self._funcParams:
                            for attachment in x.attachments:
                                if attachment.photo:
                                    attachedPhotos.append(attachment.photo.sizes[-1].url)

            unpackFwd([vkMessage.reply_message] + vkMessage.fwd_messages)
            if fwd:
                fwd = '!@next!@'.join(fwd)
                msg = f'{msg} {fwd}'

            msg = self._tagsFormatter.format(msg)
            funcArgs = {}
            if '_id' in self._funcParams:
                funcArgs.update({'_id': vkMessage.from_id})
            if 'msg' in self._funcParams:
                funcArgs.update({'msg': msg})
            if 'fwdNames' in self._funcParams:
                fwdNamesIds = [fwdNames[x] for x in range(len(fwdNames))]

                tmp = {}
                [tmp.update({x.id: {'firstName': x.first_name, 'lastName': x.last_name}}) for x in
                 (await self._apiMethods['getUsers'](fwdNames)).response]
                for i in range(len(fwdNamesIds)):
                    fwdNamesIds[i] = tmp[fwdNamesIds[i]]
                funcArgs.update({'fwdNames': fwdNamesIds})
            if 'attachedPhotos' in self._funcParams:
                funcArgs.update({'attachedPhotos': attachedPhotos})
            if 'attachedDocs' in self._funcParams:
                funcArgs.update({'attachedDocs': [x.doc.url for x in vkMessage.attachments]})

            try:
                r = await self._func(**funcArgs)
            except Exception as e:
                logger.error(e)
                r = [('Произошла непредвиденная ошибка. Скорее всего это вызвано неправильным использованием одной из'
                      'команд. Если это не так, то будь другом, напиши [id560302519|разработчику бота]. Спасибо.')]

            try:
                for msg in r:
                    if type(msg) is self._imageType:
                        if msg.url:
                            await self._apiMethods['sendImagesFromURLs'](vkMessage.peer_id,
                                                                         [msg.url], userId)
                        elif msg.filepath:
                            await self._apiMethods['sendImagesFromFiles'](vkMessage.peer_id,
                                                                          [msg.filepath], userId)
                    elif type(msg) is self._docType:
                        await self._apiMethods['sendDocs'](vkMessage.from_id, [msg.filepath])
                    elif type(msg) is str:
                        await self._apiMethods['sendText'](vkMessage.peer_id, [msg])
            except APIError:
                await self._apiMethods['sendText'](vkMessage.peer_id,
                                                   [("Начни переписку со мной, чтобы я мог отправлять тебе вложения."
                                                     "И желательно подпишись 😏")
                                                    ])

    async def _regHandler(self, h: type) -> None:
        eventTypeFilter = EventTypeFilter(BotEventType.MESSAGE_NEW)

        class TextFilter(BaseFilter):
            def __init__(self, h):
                super().__init__()
                self.h = h

            async def check(self, event: BotEvent) -> FilterResult:
                msg = event.object.object.message.text.lower()
                if event.object.object.message.from_id != event.object.object.message.peer_id:
                    msg = msg[1:]
                return FilterResult(await self.h.filter(msg))

        textFilter = TextFilter(h)
        handler = self._router.registrar.new()
        handler.filters = [eventTypeFilter, textFilter]
        hArgs = {}
        hParams = signature(h).parameters
        if 'imgSearch' in hParams:
            hArgs.update({'imgSearch': self._imgSearch})
        if 'dbConnection' in hParams:
            hArgs.update({'dbConnection': self._dbConnection})
        hI = h(**hArgs)
        h = self._Callback(
            hI.run, self._Handler.Image, self._apiMethods, self._rateLimit.ratecounter, self._Handler.Doc
        )
        handler.callback = h
        ready = handler.ready()
        self._router.registrar.register(ready)
