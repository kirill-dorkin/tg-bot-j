import types
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
async def test_conflict_suppressed():
    bot = DummyBot()
    gen = Dispatcher._listen_updates(bot)
    updates = [u async for u in gen]
    assert updates == []
