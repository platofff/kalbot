import asyncio
import logging
import os
import sys
from threading import Thread

from backends.vkwave.bot import Bot as VkwaveBot
from abstract.database import Database

backends = ['vkwave']

try:
    if os.environ['DEBUG'] in ['1', 'true']:
        logging.basicConfig(level=logging.DEBUG)
except KeyError:
    pass

try:
    backends = os.environ['BACKENDS'].split(',')
except KeyError:
    pass

os.chdir(sys.path[0])


class LoopThread(Thread):
    def __init__(self, loop):
        Thread.__init__(self)
        self.loop = loop

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


async def main():
    if 'vkwave' in backends:
        db = Database()
        await VkwaveBot.create(db.con)
    else:
        raise Exception('Unsupported backend!')

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loopThread = LoopThread(loop)
    loopThread.start()
    loop.call_soon_threadsafe(asyncio.ensure_future, main())
