import asyncio
from types import SimpleNamespace

import pytest

from aiogram.exceptions import TelegramConflictError
from aiogram.methods import GetUpdates

from app.infra.dispatcher import Dispatcher


class DummyBot:
    def __init__(self):
        self.session = SimpleNamespace(timeout=None)
        self.id = 42

    async def __call__(self, method, **kwargs):  # pragma: no cover - network not used
        raise TelegramConflictError(GetUpdates(), "conflict")


@pytest.mark.asyncio
async def test_conflict_retries(monkeypatch):
    async def fast_sleep(_):
        pass

    monkeypatch.setattr("app.infra.dispatcher.asyncio.sleep", fast_sleep)
    bot = DummyBot()
    gen = Dispatcher._listen_updates(bot, polling_timeout=0)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(anext(gen), 0.01)
    await gen.aclose()
