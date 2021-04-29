import json
import logging
import operator
import re
from time import sleep
from typing import List
from urllib import request, parse as urllib_parse
from urllib.error import HTTPError

from cachetools import LFUCache, cachedmethod

logger = logging.getLogger(__name__)


class ImgSearch:
    def __init__(self):
        self._cache = LFUCache(maxsize=128)
        self._url = 'https://duckduckgo.com/'
        self._requestUrl = self._url + "i.js"
        self._headers = {
            'authority': 'duckduckgo.com',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'sec-fetch-dest': 'empty',
            'x-requested-with': 'XMLHttpRequest',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/80.0.3987.163 Safari/537.36',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'referer': 'https://duckduckgo.com/',
            'accept-language': 'en-US,en;q=0.9',
        }

    @classmethod
    def _getImages(cls, objs: dict):
        images = []
        for obj in objs:
            if obj["image"].endswith(('.gif', '.jpg', '.png', '.jpeg')):
                images.append(obj["image"])
        return images

    @cachedmethod(operator.attrgetter('_cache'))
    def search(self, keywords: str) -> List[str]:
        params = {
            'q': keywords,
            't': 'ht',
            'iax': 'common',
            'ia': 'common'
        }
        logger.debug("Hitting DuckDuckGo for Token")

        #   First make a request to above URL, and parse out the 'vqd'
        #   This is a special token, which should be used in the subsequent request
        res = request.urlopen(
            request.Request(
                self._url, data=urllib_parse.urlencode(params).encode()
            )
        ).read().decode('utf-8')

        search_obj = re.search(r'vqd=([\d-]+)\&', res, re.M | re.I)

        if not search_obj:
            logger.debug("Token Parsing Failed !")
            return []

        logger.debug("Obtained Token")

        params = {
            'l': 'us-en',
            'o': 'json',
            'q': keywords,
            'vqd': search_obj.group(1),
            'f': ',,,',
            'p': '1',
            'v7exp': 'a',
        }

        logger.debug("Hitting Url : %s", self._requestUrl)

        while True:
            try:
                data = json.loads(
                    request.urlopen(
                        request.Request(
                            f'{self._requestUrl}?{urllib_parse.urlencode(params).encode()}',
                            headers=self._headers)
                    ).read().decode('utf-8')
                )
            except HTTPError:
                sleep(5)
                continue
            finally:
                break

        logger.debug("Hitting Url Success : %s", self._requestUrl)
        return self._getImages(data["results"])
