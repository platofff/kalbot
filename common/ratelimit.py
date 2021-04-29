from datetime import datetime
from math import ceil
from sys import getsizeof
from typing import Union


class RateLimit:
    _recent: dict = {}

    def __init__(self, limit_sec):
        self._limit_sec = limit_sec

    async def _clean(self, now: float):
        for user in list(self._recent):
            try:
                if self._recent[user] < now:
                    self._recent.pop(user)
            except KeyError:
                break

    async def ratecounter(self, _id: str) -> Union[int, str]:
        async def clean():
            if getsizeof(self._recent) > 1024:
                await self._clean(now)
        now = datetime.now().timestamp()
        if _id in self._recent.keys() and self._recent[_id] > now:
            self._recent[_id] += self._limit_sec
            await clean()
            return f'Не так быстро! Жди {ceil(self._recent[_id] - now)} секунд.'
        else:
            self._recent[_id] = now + self._limit_sec
            await clean()
            return True
