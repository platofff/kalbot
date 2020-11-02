import asyncio
import re
import traceback
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

from vkwave.types.objects import DocsDocAttachmentType

path.append("...")
from abstract.bot import Bot as AbstractBot

logger = logging.getLogger("VK-Wave")
loop: asyncio.AbstractEventLoop


class Bot(AbstractBot):
    _apiMethods: dict = {}

    async def _APIsendImagesFromURLs(self, peer_id: int, urls: list, user_id=None) -> None:
        attachment = await self._photoUploader.get_attachments_from_links(links=urls, peer_id=user_id)
        await self._apiSession.get_context().messages.send(
            peer_id=peer_id, attachment=attachment, random_id=0
        )

    async def _APIsendImagesFromFiles(self, peer_id: int, files: list, user_id=None) -> None:
        attachment = await self._photoUploader.get_attachments_from_paths(file_paths=files, peer_id=user_id)
        await self._apiSession.get_context().messages.send(
            peer_id=peer_id, attachment=attachment, random_id=0
        )
        for f in files:
            remove(f)

    async def _APIsendText(self, user_id: int, text: str) -> None:
        await self._apiSession.get_context().messages.send(
            peer_id=user_id, message=text, random_id=0
        )

    async def _APIsendDocs(self, user_id: int, files: list) -> None:
        attachment = await self._docUploader.get_attachments_from_paths(file_paths=files, peer_id=user_id)
        await self._apiSession.get_context().messages.send(
            peer_id=user_id, attachment=attachment, random_id=0
        )

    async def _APIgetUsers(self, user_ids: list) -> dict:
        return await self._apiSession.get_context().users.get(user_ids=user_ids)

    async def _APIgetGroups(self, group_ids: list) -> dict:
        return await self._apiSession.get_context().groups.get_by_id(group_ids=group_ids)

    async def _APIgetMessagesById(self, messages_ids: list) -> list:
        return (await self._apiSession.get_context().messages.get_by_id(message_ids=messages_ids)).response.items

    def __init__(self, db_connection: pymysql.connections.Connection):
        AbstractBot.__init__(self, db_connection)
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
    async def create(cls, db_connection: pymysql.connections.Connection, _loop: asyncio.AbstractEventLoop):
        global loop
        self = Bot(db_connection)
        loop = _loop
        await self._regHandlers()
        await self._dp.cache_potential_tokens()
        await self._lpExtension.start()
        return self

    class _Callback:
        class TagsFormatter:
            @classmethod
            def _get(cls, match: re.Match) -> str:
                return re.sub(r'\[.*\|', '', match.group(0))[:-1]

            def format(self, msg: str) -> str:
                return re.sub(r'\[.*?\|.*?\]', self._get, msg)

        def __init__(self, func: Callable[[int, str, list, None], list], image_type: type,
                     api_methods: dict, rate_counter: Callable[[int], Awaitable[bool]], doc_type: type):
            self._func = func
            self._imageType = image_type
            self._docType = doc_type
            self._apiMethods = api_methods
            self._rateCounter = rate_counter
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
            if 'attached_photos' in self._funcParams:
                for attachment in vkMessage.attachments:
                    if attachment.photo:
                        attachedPhotos.append(attachment.photo.sizes[-1].url)

            fwd = []
            fwdNames = []
            fwdMsgs = []

            def unpackFwd(msgs):
                for x in msgs:
                    if x and x not in fwdMsgs:
                        if x.text:
                            fwd.append(x.text)
                            fwdNames.append(x.from_id)
                        if x.fwd_messages:
                            unpackFwd(x.fwd_messages)
                        if 'attached_photos' in self._funcParams:
                            for _attachment in x.attachments:
                                if _attachment.photo:
                                    attachedPhotos.append(_attachment.photo.sizes[-1].url)
                        fwdMsgs.append(x)

            unpackFwd([vkMessage.reply_message] + vkMessage.fwd_messages)
            if fwd:
                msg = f'{msg} {"!@next!@".join(fwd)}'

            msg = self._tagsFormatter.format(msg)
            funcArgs = {}
            if '_id' in self._funcParams:
                funcArgs.update({'_id': vkMessage.from_id})
            if 'msg' in self._funcParams:
                funcArgs.update({'msg': msg})
            if 'fwd_names' in self._funcParams:
                fwdNamesIds = [fwdNames[x] for x in range(len(fwdNames))]

                tmp = {}
                [tmp.update({x.id: {'firstName': x.first_name, 'lastName': x.last_name}}) for x in
                 (await self._apiMethods['getUsers'](fwdNames)).response]
                for i in range(len(fwdNamesIds)):
                    fwdNamesIds[i] = tmp[fwdNamesIds[i]]
                funcArgs.update({'fwd_names': fwdNamesIds})
            if 'attached_photos' in self._funcParams:
                funcArgs.update({'attached_photos': attachedPhotos})
            if 'attached_docs' in self._funcParams:
                funcArgs.update({'attached_docs': [x.doc.url for x in vkMessage.attachments]})
            if 'attached_voice' in self._funcParams:
                try:
                    funcArgs.update({'attached_voice': (lambda: vkMessage.attachments[0]
                    if vkMessage.attachments[0].doc.type == DocsDocAttachmentType.AUDIO_MESSAGE else None)()})
                except (IndexError, KeyError):
                    pass

            async def postResult(r: list):
                try:
                    for message in r:
                        if type(message) is self._imageType:
                            if message.url:
                                await self._apiMethods['sendImagesFromURLs'](vkMessage.peer_id,
                                                                             [message.url], userId)
                            elif message.filepath:
                                await self._apiMethods['sendImagesFromFiles'](vkMessage.peer_id,
                                                                              [message.filepath], userId)
                        elif type(message) is self._docType:
                            await self._apiMethods['sendDocs'](vkMessage.from_id, [message.filepath])
                        elif type(message) is str:
                            await self._apiMethods['sendText'](vkMessage.peer_id, [message])
                except APIError:
                    await self._apiMethods['sendText'](vkMessage.peer_id,
                                                       [('Начни переписку со мной, чтобы я мог отправлять тебе '
                                                         'вложения. И желательно подпишись 😏')])

            try:
                if ('callback' and 'loop') in self._funcParams:
                    funcArgs.update({'loop': loop, 'callback': postResult})
                    self._func(**funcArgs)
                else:
                    await postResult(self._func(**funcArgs))
            except Exception as e:
                logger.error(f'Unexcepted error while command execution: {e}\n{traceback.format_exc()}')
                await postResult([('Произошла непредвиденная ошибка. Скорее всего это вызвано неправильным '
                                   'использованием одной из команд. Если это не так, то будь другом, напиши '
                                   '[id560302519|разработчику бота]. Спасибо.')])

    async def _regHandler(self, h: _Callback) -> None:
        eventTypeFilter = EventTypeFilter(BotEventType.MESSAGE_NEW)

        class TextFilter(BaseFilter):
            def __init__(self, _h):
                super().__init__()
                self.h = _h

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
        if 'img_search' in hParams:
            hArgs.update({'img_search': self._imgSearch})
        if 'db_connection' in hParams:
            hArgs.update({'db_connection': self._dbConnection})
        hI = h(**hArgs)
        h = self._Callback(
            hI.run, self._Handler.Image, self._apiMethods, self._rateLimit.ratecounter, self._Handler.Doc
        )
        handler.callback = h
        ready = handler.ready()
        self._router.registrar.register(ready)
