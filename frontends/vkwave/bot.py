import asyncio
import logging
import re
import traceback
from inspect import signature
from os import environ, remove
from sys import path
from typing import Callable, Awaitable

import pymysql
import yaml
from vkwave.api import Token, BotSyncSingleToken, API
from vkwave.api.methods._error import APIError
from vkwave.bots import TokenStorage, GroupId, Dispatcher, BotLongpollExtension, PhotoUploader, DefaultRouter, \
    EventTypeFilter, BotEvent, BaseEvent, DocUploader
from vkwave.bots.core import BaseFilter
from vkwave.bots.core.dispatching.filters.base import FilterResult
from vkwave.client import AIOHTTPClient
from vkwave.longpoll import BotLongpollData, BotLongpoll
from vkwave.types.bot_events import BotEventType

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

    async def _APIsendDocs(self, user_id: int, files: list) -> None:
        attachment = await self._docUploader.get_attachments_from_paths(file_paths=files, peer_id=user_id)
        await self._apiSession.get_context().messages.send(
            peer_id=user_id, attachment=attachment, random_id=0
        )
    '''
    async def _APIgetGroups(self, group_ids: list) -> dict:
        return await self._apiSession.get_context().groups.get_by_id(group_ids=group_ids)

    async def _APIgetMessagesById(self, messages_ids: list) -> list:
        return (await self._apiSession.get_context().messages.get_by_id(message_ids=messages_ids)).response.items
    '''
    def __init__(self, db_connection: pymysql.connections.Connection):
        AbstractBot.__init__(self, db_connection)
        if not ('VK_BOT_TOKEN' in environ):
            with open('vkapi.yaml') as c:
                config = yaml.safe_load(c)
                bot_token = Token(config["bot_token"])
                self._gid = config["group_id"]
        else:
            bot_token = Token(environ['VK_BOT_TOKEN'])
            self._gid = int(environ['VK_BOT_GID'])

        client = AIOHTTPClient()
        token = BotSyncSingleToken(bot_token)
        self._apiSession = API(token, client)
        api = self._apiSession.get_context()
        lp_data = BotLongpollData(self._gid)
        longpoll = BotLongpoll(api, lp_data)
        token_storage = TokenStorage[GroupId]()
        self._dp = Dispatcher(self._apiSession, token_storage)
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
            self.func = func
            self._imageType = image_type
            self._docType = doc_type
            self._apiMethods = api_methods
            self._rateCounter = rate_counter
            self._tagsFormatter = self.TagsFormatter()
            self.funcParams = signature(self.func).parameters

        async def execute(self, event: BaseEvent) -> None:
            vk_message = event.object.object.message
            if vk_message.is_cropped:
                if vk_message.from_id != vk_message.peer_id:
                    await event.api_ctx.messages.send(peer_id=vk_message.peer_id,
                                                      message='Твое сообщение слишком большое, '
                                                              'попробуй написать мне в ЛС!',
                                                      random_id=0)
                    return None
                vk_message = (await event.api_ctx.messages.get_by_id(message_ids=[vk_message.id])).response.items[0]
            if not await self._rateCounter(vk_message.from_id):
                logger.debug(f"Oh shit, I'm sorry: {vk_message.from_id} is banned.")
                return None
            msg = vk_message.text
            if vk_message.from_id != vk_message.peer_id:
                user_id = vk_message.from_id
                msg = msg[1:]
            else:
                user_id = None
            attached_photos = []
            if 'attached_photos' in self.funcParams:
                for attachment in vk_message.attachments:
                    if attachment.photo:
                        attached_photos.append(attachment.photo.sizes[-1].url)

            fwd = []
            fwd_names = []
            fwd_msgs = []

            def unpackFwd(msgs):
                for x in msgs:
                    if x and x not in fwd_msgs:
                        if x.text:
                            fwd.append(x.text)
                            fwd_names.append(x.from_id)
                        if x.fwd_messages:
                            unpackFwd(x.fwd_messages)
                        if 'attached_photos' in self.funcParams:
                            for _attachment in x.attachments:
                                if _attachment.photo:
                                    attached_photos.append(_attachment.photo.sizes[-1].url)
                        fwd_msgs.append(x)

            unpackFwd([vk_message.reply_message] + vk_message.fwd_messages)
            if fwd:
                msg = f'{msg} {"!@next!@".join(fwd)}'

            msg = self._tagsFormatter.format(msg)
            func_args = {}
            if '_id' in self.funcParams:
                func_args.update({'_id': vk_message.from_id})
            if 'msg' in self.funcParams:
                func_args.update({'msg': msg})
            if 'fwd_names' in self.funcParams:
                fwd_names_ids = [fwd_names[x] for x in range(len(fwd_names))]

                tmp = {}
                [tmp.update({x.id: {'firstName': x.first_name, 'lastName': x.last_name}}) for x in
                 (await event.api_ctx.users.get(user_ids=fwd_names)).response]
                for i in range(len(fwd_names_ids)):
                    fwd_names_ids[i] = tmp[fwd_names_ids[i]]
                func_args.update({'fwd_names': fwd_names_ids})
            if 'attached_photos' in self.funcParams:
                func_args.update({'attached_photos': attached_photos})
            if 'attached_docs' in self.funcParams:
                func_args.update({'attached_docs': [x.doc.url for x in vk_message.attachments]})

            async def postResult(r: list):
                try:
                    for message in r:
                        if type(message) is self._imageType:
                            if message.url:
                                await self._apiMethods['sendImagesFromURLs'](vk_message.peer_id,
                                                                             [message.url], user_id)
                            elif message.filepath:
                                await self._apiMethods['sendImagesFromFiles'](vk_message.peer_id,
                                                                              [message.filepath], user_id)
                        elif type(message) is self._docType:
                            await self._apiMethods['sendDocs'](vk_message.from_id, [message.filepath])
                        elif type(message) is str:
                            await event.api_ctx.messages.send(peer_id=vk_message.peer_id, message=message, random_id=0)
                except APIError:
                    await event.api_ctx.messages.send(
                        peer_id=vk_message.peer_id, message='Начни переписку со мной, чтобы я мог отправлять тебе '
                                                            'вложения. И желательно подпишись 😏', random_id=0
                    )

            try:
                if ('callback' and 'loop') in self.funcParams:
                    func_args.update({'loop': loop, 'callback': postResult})
                    self.func(**func_args)
                else:
                    await postResult(self.func(**func_args))
            except Exception as e:
                logger.error(f'Unexcepted error while command execution: {e}\n{traceback.format_exc()}')
                await postResult([('Произошла непредвиденная ошибка. Скорее всего это вызвано неправильным '
                                   'использованием одной из команд. Если это не так, то будь другом, напиши '
                                   '[id560302519|разработчику бота]. Спасибо.')])

    async def _regHandler(self, h: _Callback) -> None:
        event_type_filter = EventTypeFilter(BotEventType.MESSAGE_NEW)

        class TextFilter(BaseFilter):
            def __init__(self, _h):
                super().__init__()
                self.h = _h

            async def check(self, event: BotEvent) -> FilterResult:
                msg = event.object.object.message.text.lower()
                if event.object.object.message.from_id != event.object.object.message.peer_id:
                    msg = msg[1:]
                func_params = signature(self.h.filter).parameters
                func_arguments = {}
                if 'msg' in func_params:
                    func_arguments.update({'msg': msg})
                if 'voice' in func_params:
                    try:
                        if event.object.object.message.attachments[0].audio_message:
                            if event.object.object.message.peer_id == 2000000014:
                                func_arguments.update({'voice': True})
                            else:
                                return FilterResult(False)
                        else:
                            func_arguments.update({'voice': False})
                    except (KeyError, IndexError):
                        pass
                return FilterResult(await self.h.filter(**func_arguments))

        text_filter = TextFilter(h)
        handler = self._router.registrar.new()
        handler.filters = [event_type_filter, text_filter]
        h_args = {}
        h_params = signature(h).parameters
        if 'img_search' in h_params:
            h_args.update({'img_search': self._imgSearch})
        if 'db_connection' in h_params:
            h_args.update({'db_connection': self._dbConnection})
        h_i = h(**h_args)
        h = self._Callback(
            h_i.run, self._Handler.Image, self._apiMethods, self._rateLimit.ratecounter, self._Handler.Doc
        )
        handler.callback = h
        ready = handler.ready()
        self._router.registrar.register(ready)
