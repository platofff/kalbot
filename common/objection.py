import base64
import json
import random
from string import ascii_letters

from typing import List, Dict, Union

import aiohttp
import aioredis

from common.ratelimit import RateLimit


class Objection:
    http: aiohttp.ClientSession
    _usage: str
    _rateLimit: RateLimit
    _db: aioredis.commands.Redis
    _jsonPattern: Dict[str, Union[int, bool, str]]

    @classmethod
    async def new(cls, redis_uri: str):
        self = Objection()
        self._jsonPattern = {
            "id": -1,
            "text": "",
            "poseId": 1,
            "poseAnimation": True,
            "flipped": False,
            "bubbleType": "0",
            "goNext": False,
            "mergeNext": False,
            "doNotTalk": False,
            "username": ""
        }
        self._usage = 'Использование только с пересланными сообщениями.'
        self._db = await aioredis.create_redis_pool(redis_uri, db=2)
        self._rateLimit = RateLimit(60)
        self.http = aiohttp.ClientSession()
        return self

    async def create(self, messages: List[List[Union[str, List[Union[str, Dict[str, Union[str, bool]]]]]]],
                     user_id: str) -> Union[bytes, str]:
        r = await self._rateLimit.ratecounter(user_id)
        if type(r) != bool:
            return r
        result = []
        tr = self._db.multi_exec()
        for author in messages:
            tr.get(f'{user_id}_{author[0]}')
        poses = [int(x) if x else None for x in await tr.execute()]
        for i in range(len(poses)):
            phrase = self._jsonPattern.copy()
            phrase['username'] = messages[i][0]
            for content in messages[i][1]:
                if type(content) == str:
                    phrase['text'] = content
                else:
                    content.update({'name': ''.join([random.choice(ascii_letters) for _ in range(8)])})
                    async with self.http.post('https://api.objection.lol/api/assets/evidence/add',
                                              data=json.dumps(content, ensure_ascii=False),
                                              headers={
                                                  'Content-type': 'application/json',
                                                  'Referer': 'https://objection.lol/',
                                                  'Origin': 'https://objection.lol/',
                                                  'Authorization': 'Bearer undefined',
                                                  'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:87.0) '
                                                                'Gecko/20100101 Firefox/87.0'
                                              }) as resp:
                        phrase['text'] += f'[#evd{await resp.text()}][#p1000][#evdh]'
            if poses[i]:
                phrase['poseId'] = poses[i]
            result.append(phrase)
        return base64.b64encode(bytes(json.dumps(result, ensure_ascii=False), 'utf8'))

    async def conf(self, data: str, user_id: str):
        objection = json.loads(base64.b64decode(data))
        tr = self._db.multi_exec()
        processed = {}
        for phrase in objection:
            if not phrase["username"] in processed:
                tr.set(f'{user_id}_{phrase["username"]}', phrase['poseId'])
                processed.update({phrase["username"]: phrase['poseId']})
        await tr.execute()
        return '\n'.join([f'Персонажу {key} назначается поза {value}' for key, value in processed.items()])
