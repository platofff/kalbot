import json
import logging
import operator
import re
import time

import requests
from cachetools import TTLCache, cachedmethod

logger = logging.getLogger(__name__)


class ImgSearch:
    def __init__(self):
        self.cache = TTLCache(ttl=600, maxsize=65536)
        self.url = 'https://duckduckgo.com/'
        self.headers = {
            'authority': 'duckduckgo.com',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'sec-fetch-dest': 'empty',
            'x-requested-with': 'XMLHttpRequest',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'referer': 'https://duckduckgo.com/',
            'accept-language': 'en-US,en;q=0.9',
        }

    def _getImages(self, objs):
        images = []
        for obj in objs:
            if obj["image"][-4:] in [".gif", ".jpg", ".png"] or obj["image"][-5:] == ".jpeg":
                images.append(obj["image"])
        return images

    @cachedmethod(operator.attrgetter('cache'))
    def fetch(self, keywords):
        result = []

        params = {
            'q': keywords,
            't': 'ht',
            'iax': 'images',
            'ia': 'images'
        }
        logger.debug("Hitting DuckDuckGo for Token")

        #   First make a request to above URL, and parse out the 'vqd'
        #   This is a special token, which should be used in the subsequent request
        res = requests.post(self.url, data=params)
        searchObj = re.search(r'vqd=([\d-]+)\&', res.text, re.M | re.I)

        if not searchObj:
            logger.debug("Token Parsing Failed !")
            return result

        logger.debug("Obtained Token")

        params = (
            ('l', 'us-en'),
            ('o', 'json'),
            ('q', keywords),
            ('vqd', searchObj.group(1)),
            ('f', ',,,'),
            ('p', '1'),
            ('v7exp', 'a'),
        )

        requestUrl = self.url + "i.js"

        logger.debug("Hitting Url : %s", requestUrl)

        while True:
            while True:
                try:
                    res = requests.get(requestUrl, headers=self.headers, params=params)
                    data = json.loads(res.text)
                    break
                except ValueError as e:
                    logger.debug("Hitting Url Failure - Sleep and Retry: %s", requestUrl)
                    time.sleep(5)
                    continue

            logger.debug("Hitting Url Success : %s", requestUrl)
            result += self._getImages(data["results"])

            if "next" not in data:
                logger.debug("No Next Page - Exiting")
                return result

            requestUrl = self.url + data["next"]
