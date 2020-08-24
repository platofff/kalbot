import asyncio
import logging
import os
import sys

from backends.vkwave.bot import Bot as VkwaveBot

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

#os.chdir(sys.path[0])
os.chdir('/home/arkadiy/PycharmProjects/kalbot')

async def main():
    if 'vkwave' in backends:
        await VkwaveBot.create()
    else:
        raise Exception('Unsupported backend!')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
