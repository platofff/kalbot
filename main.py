#!/usr/bin/env python3
import asyncio
import concurrent.futures
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor
from os import environ
import logging
import random
from typing import Optional, Tuple, List, Union
import re

import typing
from vkbottle import Bot, DocMessagesUploader
from vkbottle.bot import Message
from vkbottle.tools.dev_tools.uploader import PhotoMessageUploader
from vkbottle_types.objects import MessagesMessageAttachmentType, PhotosPhotoSizesType, MessagesForeignMessage, \
    MessagesMessage

from common.demotivator import Demotivator
from common.nouveau import Nouveau
from common.objection import Objection
from common.optimisation import bash_encode
from common.searchimages import ImgSearch
from common.tagsformatter import TagsFormatter
from common.vasyacache import Vasya
from common.ratelimit import RateLimit

level = logging.INFO
try:
    if environ['DEBUG'] == '1':
        level = logging.DEBUG
        import pystuck

        pystuck.run_server()
except KeyError:
    level = logging.INFO

logging.basicConfig(level=level)
logger = logging.getLogger('MAIN')

bot = Bot(environ['VK_BOT_TOKEN'])
redis_uri = environ['REDIS_URI']
photo_uploader = PhotoMessageUploader(bot.api, generate_attachment_strings=True)
docs_uploader = DocMessagesUploader(bot.api, generate_attachment_strings=True)
pool = ProcessPoolExecutor()
demotivator = Demotivator()
img_search = ImgSearch()
rate_limit = RateLimit(5)
objection: Objection
vasya_caching: Vasya


def get_arguments(text: str):
    return re.sub(r'^[\S]*\s?', '', text, 1)


@bot.on.message(text=['/начать', '/start', '/команды', '/commands', '/помощь', '/help'])
async def start_handler(message: Message):
    await message.answer('Команды:\n'
                         '/демотиватор - сгенерировать демотиватор со своей картинкой или из интернета. При вызове без '
                         'аргументов текст берётся из БД Васи Машинки https://vk.com/vasyamashinka\n'
                         '/оптимизация - сгенерировать скрипт оптимизации Ubuntu\n'
                         '/nouveau <уровень шакализации, когда не указан = 93> - рендер картинки с помощью '
                         'проприетарного драйвера nouveau\n'
                         '/objection; /objectionconf - Генерация суда в Ace Attorney из пересланных сообщений. Как '
                         'пользоваться тут: https://vk.com/@kallinux-objection')


async def get_photo_url(message: Union[Message, MessagesForeignMessage]):
    url = None
    if message.attachments[0].type == MessagesMessageAttachmentType.PHOTO:
        # If possible get proportional image
        for size in reversed(message.attachments[0].photo.sizes):
            if size.type not in (PhotosPhotoSizesType.R, PhotosPhotoSizesType.Q, PhotosPhotoSizesType.P,
                                 PhotosPhotoSizesType.O):
                url = size.url
                break
        if not url:
            url = message.attachments[0].photo.sizes[-1].url
    return url


async def unpack_fwd(message: Union[Message, MessagesMessage], photos_max: Optional[Union[int, bool]] = 1) -> \
        Tuple[typing.OrderedDict[int, str], typing.OrderedDict[int, List[str]], typing.OrderedDict[int, int]]:
    fwd = OrderedDict()
    fwd_ids = OrderedDict()
    fwd_msgs = []
    fwd_photos = OrderedDict()

    async def _unpack_fwd(msgs: List[MessagesForeignMessage]):
        for x in msgs:
            if x and x.conversation_message_id not in fwd_msgs:
                fwd_ids.update({x.conversation_message_id: x.from_id})
                if x.text:
                    fwd.update({x.conversation_message_id: x.text})
                if x.fwd_messages:
                    await _unpack_fwd(x.fwd_messages)
                if x.attachments and (not photos_max or len(fwd_photos) < photos_max):
                    photo = await get_photo_url(x)
                    if photo:
                        if x.conversation_message_id not in fwd_photos.keys():
                            fwd_photos[x.conversation_message_id] = [photo]
                        else:
                            fwd_photos[x.conversation_message_id].append(photo)
                fwd_msgs.append(x.conversation_message_id)

    await _unpack_fwd([message.reply_message] + message.fwd_messages)
    return fwd, fwd_photos, fwd_ids


def create_demotivator(args: list, url: Optional[str] = None) -> bytes:
    search_results = None

    def kernel_panic():
        _search_results = img_search.search('kernel panic')
        return _search_results, random.choice(search_results)

    if not url:
        search_results = img_search.search(args[0])
        if search_results:
            url = random.choice(search_results)
        else:
            search_results, url = kernel_panic()

    while True:
        dem = demotivator.create(url, args[0], args[1:])
        if dem:
            return dem
        else:
            search_results.pop(search_results.index(url))
            if search_results:
                url = random.choice(search_results)
            else:
                search_results, url = kernel_panic()


@bot.on.message(text=['/демотиватор', '/demotivator', '/демотиватор <_>', '/demotivator <_>'])
async def demotivator_handler(message: Message, _: Optional[str] = None):
    r = await rate_limit.ratecounter(f'vk{message.from_id}')
    if type(r) != bool:
        await message.answer(r)
        return None

    fwd, fwd_photos, _ = await unpack_fwd(message)
    fwd = '\n'.join([*fwd.values()])
    text = get_arguments(message.text)

    def callback(_fut: concurrent.futures.Future):
        async def _callback(result):
            await message.answer(attachment=await photo_uploader.upload(result))
        asyncio.ensure_future(_callback(_fut.result()), loop=bot.loop)

    if not text and not fwd:
        await message.answer(attachment=await photo_uploader.upload(await vasya_caching.get_demotivator()))
    else:
        if fwd and text:
            text += f'\n{fwd}'
        elif fwd and not text:
            text = fwd
        text = TagsFormatter.format(text)
        url = None
        if message.attachments:
            url = await get_photo_url(message)
        elif fwd_photos:
            url = [*fwd_photos.values()][0][0]

        fut = pool.submit(create_demotivator, text.splitlines(), url)
        fut.add_done_callback(callback)


@bot.on.message(text=['/nouveau', '/нуво', '/ноувеау', '/nouveau <text>', '/нуво <text>', '/ноувеау <text>'])
async def nouveau_handler(message: Message, text: Optional[str] = None):
    if not message.attachments:
        _, photos, _ = await unpack_fwd(message)
        try:
            photo = list(photos.values())[0][0]
        except IndexError:
            await message.answer('Прикрепи или перешли изображение.')
            return
    else:
        photo = await get_photo_url(message)

    try:
        q = int(text)
        if not 1 <= q <= 100:
            raise ValueError
    except ValueError:
        await message.answer('Качество картинки должно быть целым числом от 1 до 100.')
        return
    except TypeError:  # text == None
        q = 93

    q = 101 - q

    await message.answer(attachment=
                         await photo_uploader.upload(
                             await bot.loop.run_in_executor(pool, Nouveau.create, photo, q)))


@bot.on.message(text=['/оптимизация', '/optimization', '/оптимизация <text>', '/optimization <text>'])
async def optimization_handler(message: Message, text: Optional[str] = None):
    try:
        await message.answer(bash_encode(text))
    except Exception as e:
        if e.args == (914, 'Message is too long'):
            await message.answer('Слишком длинное выражение')
        else:
            raise e


@bot.on.message(text=['/обжекшон', '/objection'])
async def objection_handler(message: Message):
    if message.is_cropped:
        if message.from_id != message.peer_id:
            await message.answer('Твоё сообщение слишком большое, попробуй написать мне в ЛС!')
            return
        else:
            message_full = (await bot.api.messages.get_by_id([message.get_message_id()])).items[0]
    else:
        message_full = None

    fwd, fwd_photos, fwd_ids = await unpack_fwd(message_full if message_full else message, photos_max=False)
    if not fwd_ids:
        await message.answer('Прочитай как пользоваться: https://vk.com/@kallinux-objection')
        return
    messages = []
    users = {}
    user_ids, group_ids = [], []
    for _id in [*fwd_ids.values()]:
        if _id > 0:
            user_ids.append(str(_id))
        else:
            group_ids.append(_id)
    users_resp = await bot.api.users.get(user_ids)
    groups_resp = bot.api.groups.get_by_id([str(-x) for x in group_ids])
    for user in users_resp:
        users.update({user.id: f"{user.first_name} {user.last_name[:1]}."})
    groups_resp = await groups_resp
    for group in groups_resp:
        users.update({-group.id: group.name})

    for key, value in fwd_ids.items():
        new_val = []
        if key in fwd.keys():
            new_val.append(TagsFormatter.format(fwd[key]))
        if key in fwd_photos.keys():
            for photo_url in fwd_photos[key]:
                new_val.append({'url': photo_url, 'isIcon': False})
        if new_val:
            messages.append([users[value], new_val])

    result = await objection.create(messages, f'vk{message.from_id}')
    if type(result) == bytes:
        await message.answer('Загрузи этот файл на objection.lol/maker',
                             attachment=await docs_uploader.upload(f'Your objection.objection',
                                                                   result,
                                                                   peer_id=message.peer_id))
    else:
        await message.answer(result)


@bot.on.message(text=['/обжекшонконф', '/objectionconf'])
async def objection_conf_handler(message: Message):
    try:
        async with objection.http.get(message.attachments[0].doc.url) as resp:
            await message.answer(
                await objection.conf(
                    await resp.text(), f'vk{message.from_id}'))
    except (IndexError, AttributeError):
        await message.answer('Прикрепи .objection файл с objection.lol/maker')


async def main():
    global objection, vasya_caching
    objection = await Objection.new(redis_uri)
    vasya_caching = await Vasya.new(demotivator, img_search, pool, redis_uri)
    bot.loop.create_task(vasya_caching.run())


if __name__ == '__main__':
    bot.loop_wrapper.add_task(main())
    bot.run_forever()
