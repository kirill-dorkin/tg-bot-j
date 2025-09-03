import pytest

from app.container import build_container
from app.infra.redis import InMemoryStore


@pytest.mark.asyncio
async def test_fallbacks_to_in_memory_store(monkeypatch):
    # Force invalid Redis URL to trigger fallback
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")
    # This flag is ignored; fallback should still happen
    monkeypatch.setenv("ALLOW_IN_MEMORY_STORE", "0")
    monkeypatch.setenv("BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")
    c = await build_container()
    assert isinstance(c.store, InMemoryStore)
