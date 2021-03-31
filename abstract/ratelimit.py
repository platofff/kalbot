from datetime import datetime


class RateLimit:
    _recent: dict = {}
    LIMIT_SEC = 5

    async def _clean(self, now: float):
        for user in list(self._recent):
            try:
                if self._recent[user] < now:
                    self._recent.pop(user)
            except KeyError:
                break

    async def ratecounter(self, _id: int) -> bool:
        now = datetime.now().timestamp()
        clean = self._clean(now)
        if _id in self._recent.keys() and self._recent[_id] > now:
            self._recent[_id] += self.LIMIT_SEC
            await clean
            return False
        else:
            self._recent[_id] = now + self.LIMIT_SEC
            await clean
            return True
