from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from aiogram import loggers
from aiogram.client.bot import Bot
from aiogram.dispatcher.dispatcher import (
    DEFAULT_BACKOFF_CONFIG,
)
from aiogram.dispatcher.dispatcher import (
    Dispatcher as AiogramDispatcher,
)
from aiogram.exceptions import TelegramConflictError
from aiogram.methods import GetUpdates
from aiogram.types import Update
from aiogram.utils.backoff import Backoff, BackoffConfig

_orig_sleep = asyncio.sleep


class Dispatcher(AiogramDispatcher):
    """Dispatcher that suppresses TelegramConflictError noise."""

    @classmethod
    async def _listen_updates(
        cls,
        bot: Bot,
        polling_timeout: int = 30,
        backoff_config: BackoffConfig = DEFAULT_BACKOFF_CONFIG,
        allowed_updates: list[str] | None = None,
    ) -> AsyncGenerator[Update, None]:
        backoff = Backoff(config=backoff_config)
        get_updates = GetUpdates(timeout=polling_timeout, allowed_updates=allowed_updates)
        kwargs = {}
        if bot.session.timeout:
            kwargs["request_timeout"] = int(bot.session.timeout + polling_timeout)
        failed = False
        while True:
            try:
                updates = await bot(get_updates, **kwargs)
            except TelegramConflictError:
                loggers.dispatcher.info(
                    "Polling conflict detected; retrying... (bot id = %d)",
                    bot.id,
                )
                await asyncio.sleep(next(backoff))
                await _orig_sleep(0)
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:  # pragma: no cover - network failures
                failed = True
                loggers.dispatcher.error(
                    "Failed to fetch updates - %s: %s", type(e).__name__, e
                )
                loggers.dispatcher.warning(
                    "Sleep for %f seconds and try again... (tryings = %d, bot id = %d)",
                    backoff.next_delay,
                    backoff.counter,
                    bot.id,
                )
                await asyncio.sleep(next(backoff))
                await _orig_sleep(0)
                continue
            if failed:
                loggers.dispatcher.info(
                    "Connection established (tryings = %d, bot id = %d)",
                    backoff.counter,
                    bot.id,
                )
                backoff.reset()
                failed = False
            for update in updates:
                yield update
                get_updates.offset = update.update_id + 1
