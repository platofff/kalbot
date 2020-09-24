import asyncio
import logging
import os
import sys
from threading import Thread

from frontends.vkwave.bot import Bot as VkwaveBot
from abstract.database import Database


class LoopThread(Thread):
    def __init__(self, loop):
        Thread.__init__(self)
        self.loop = loop

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


class Application:
    _frontends: list

    def __init__(self):
        os.chdir(sys.path[0])

        try:
            if os.environ['DEBUG'] in ['1', 'true']:
                logging.basicConfig(level=logging.DEBUG)
        except KeyError:
            logging.basicConfig(level=logging.INFO)

        try:
            self._frontends = os.environ['FRONTENDS'].split(',')
        except KeyError:
            self._frontends = ['vkwave']

    async def main(self):
        if 'vkwave' in self._frontends:
            db = Database()
            await VkwaveBot.create(db.con, loop)
        else:
            raise Exception('Unsupported backend!')


if __name__ == "__main__":
    app = Application()
    loop = asyncio.new_event_loop()
    loopThread = LoopThread(loop)
    loopThread.start()
    loop.call_soon_threadsafe(asyncio.ensure_future, app.main())
