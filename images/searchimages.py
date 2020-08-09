import json
import logging
import re
import time

import requests
from cachetools import cached, TTLCache

logger = logging.getLogger(__name__)


class ImgSearch:
    @cached(cache=TTLCache(ttl=600, maxsize=65536))
    def fetch(self, keywords):
        result = []

        def getImages(objs):
            images = []
            for obj in objs:
                if obj["image"][-4:] in [".gif", ".jpg", ".png"] or obj["image"][-5:] == ".jpeg":
                    images.append(obj["image"])
            return images

        url = 'https://duckduckgo.com/'
        params = {
            'q': keywords,
            't': 'ht',
            'iax': 'images',
            'ia': 'images'
        }

        logger.debug("Hitting DuckDuckGo for Token")

        #   First make a request to above URL, and parse out the 'vqd'
        #   This is a special token, which should be used in the subsequent request
        res = requests.post(url, data=params)
        searchObj = re.search(r'vqd=([\d-]+)\&', res.text, re.M | re.I)

        if not searchObj:
            logger.error("Token Parsing Failed !")
            return -1

        logger.debug("Obtained Token")

        headers = {
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

        params = (
            ('l', 'us-en'),
            ('o', 'json'),
            ('q', keywords),
            ('vqd', searchObj.group(1)),
            ('f', ',,,'),
            ('p', '1'),
            ('v7exp', 'a'),
        )

        requestUrl = url + "i.js"

        logger.debug("Hitting Url : %s", requestUrl)

        while True:
            while True:
                try:
                    res = requests.get(requestUrl, headers=headers, params=params)
                    data = json.loads(res.text)
                    break
                except ValueError as e:
                    logger.debug("Hitting Url Failure - Sleep and Retry: %s", requestUrl)
                    time.sleep(5)
                    continue

            logger.debug("Hitting Url Success : %s", requestUrl)
            result += getImages(data["results"])

            if "next" not in data:
                logger.debug("No Next Page - Exiting")
                return result

            requestUrl = url + data["next"]
