from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Protocol, Optional

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover - optional
    Redis = None  # type: ignore


class KeyValueStore(Protocol):
    async def get(self, key: str) -> Optional[str]: ...
    async def setex(self, key: str, seconds: int, value: str) -> None: ...
    async def set_nx(self, key: str, value: str, ex: int) -> bool: ...
    async def delete(self, key: str) -> None: ...


class RedisStore:
    def __init__(self, url: str):
        if Redis is None:  # pragma: no cover - only in environments without redis
            raise RuntimeError("redis package not available")
        self._r: Redis = Redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Optional[str]:
        return await self._r.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> None:
        await self._r.setex(key, seconds, value)

    async def set_nx(self, key: str, value: str, ex: int) -> bool:
        return bool(await self._r.set(key, value, ex=ex, nx=True))

    async def delete(self, key: str) -> None:
        await self._r.delete(key)


@dataclass
class InMemoryStore:
    data: dict[str, tuple[str, float]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(self, key: str) -> Optional[str]:
        async with self.lock:
            v = self.data.get(key)
            if not v:
                return None
            value, expire = v
            if expire and expire < time.time():
                self.data.pop(key, None)
                return None
            return value

    async def setex(self, key: str, seconds: int, value: str) -> None:
        async with self.lock:
            self.data[key] = (value, time.time() + seconds)

    async def set_nx(self, key: str, value: str, ex: int) -> bool:
        async with self.lock:
            if key in self.data:
                v = self.data[key]
                if v[1] and v[1] < time.time():
                    # expired
                    self.data[key] = (value, time.time() + ex)
                    return True
                return False
            self.data[key] = (value, time.time() + ex)
            return True

    async def delete(self, key: str) -> None:
        async with self.lock:
            self.data.pop(key, None)

