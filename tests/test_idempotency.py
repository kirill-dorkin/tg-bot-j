import asyncio

import pytest

from app.infra.redis import InMemoryStore


@pytest.mark.asyncio
async def test_idempotent_apply_key():
    store = InMemoryStore()
    key = "idemp:apply:1|http://example.com"
    ok1 = await store.set_nx(key, "1", ex=300)
    ok2 = await store.set_nx(key, "1", ex=300)
    assert ok1 is True and ok2 is False

