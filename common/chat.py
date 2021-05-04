from typing import Dict, List

import aioredis


class Chat:
    _db: aioredis.commands.Redis
    commands: Dict[str, List[str]]

    @staticmethod
    async def new(redis_uri: str, commands: Dict[str, List[str]]):
        self = Chat()
        self._db = await aioredis.create_redis_pool(redis_uri, db=3)
        self.commands = {}
        for x, y in commands.items():
            for c in y:
                if ' ' in c:
                    y.remove(c)
            self.commands.update({x: y})
        return self

    async def set_limit(self, chat: str, _command: str, hour_limit: str) -> str:
        try:
            hour_limit = int(hour_limit)
        except (ValueError, TypeError):
            return 'Некорректное использование!'
        command = None
        for c, j in self.commands.items():
            if _command in j:
                command = c
                break
        if not command:
            return 'Нет такой команды!'
        if hour_limit == -1:
            await self._db.delete(f'{chat}_limit_{command}')
            return f'Лимит команды {command} для данного чата снят.'
        await self._db.set(f'{chat}_limit_{command}', hour_limit)
        return f'Лимит команды {command} для данного чата установлен на {hour_limit} вызовов на человека в час. ' \
               f'Чтобы убрать лимит установите -1.'

    async def get_limit(self, chat: str, command: str, user: str) -> int:
        configured_limit = await self._db.get(f'{chat}_limit_{command}')
        if not configured_limit:
            return -1
        configured_limit = int(configured_limit)
        key = f'{chat}_limit_{command}_{user}'
        user_limit = await self._db.get(key)
        if user_limit is not None:
            user_limit = int(user_limit)
            lim = max(0, user_limit - 1)
            ttl = await self._db.ttl(key)
            await self._db.set(key, lim, expire=ttl)
        else:
            lim = configured_limit
            await self._db.set(key, lim, expire=3600)
        return lim
