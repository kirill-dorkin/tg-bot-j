import pytest

from app.container import build_container


@pytest.mark.asyncio
async def test_requires_redis(monkeypatch):
    # Force invalid Redis URL and disallow in-memory store
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")
    monkeypatch.setenv("ALLOW_IN_MEMORY_STORE", "0")
    monkeypatch.setenv("BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")
    with pytest.raises(RuntimeError):
        await build_container()
