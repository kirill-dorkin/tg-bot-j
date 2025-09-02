from __future__ import annotations

import json
import secrets

from app.infra.redis import KeyValueStore


class ShortKeysRepo:
    def __init__(self, store: KeyValueStore):
        self.store = store

    async def generate(self, payload: dict, ttl: int = 300) -> str:
        key = secrets.token_urlsafe(8)
        await self.store.setex(f"cb:{key}", ttl, json.dumps(payload))
        return key

    async def get(self, key: str) -> dict | None:
        v = await self.store.get(f"cb:{key}")
        if not v:
            return None
        return json.loads(v)

