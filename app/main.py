from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path

from aiohttp import web
from aiogram import Router
from aiogram.exceptions import TelegramConflictError

from app.bot.handlers import health as h_health
from app.bot.handlers import actions as h_actions
from app.bot.handlers import settings as h_settings
from app.bot.handlers import search_params as h_search_params
from app.bot import anchor as h_anchor
from app.bot.middlewares import (
    I18nMiddleware,
    InjectDepsMiddleware,
    InjectSessionMiddleware,
    RateLimitMiddleware,
)
from app.container import build_container
from app.infra.redis import KeyValueStore


async def _keep_lock_alive(
    store: KeyValueStore, key: str, value: str, ttl: int
) -> None:
    """Periodically refresh distributed lock to avoid expiration."""
    while True:
        await asyncio.sleep(ttl / 2)
        try:
            await store.setex(key, ttl, value)
        except Exception:
            # Best-effort: failure to refresh shouldn't crash the bot
            pass


async def main() -> None:
    c = await build_container()
    # Acquire a simple distributed lock to avoid running multiple instances
    lock_key = "bot:lock"
    lock_ttl = 60
    lock_value = str(os.getpid())
    if not await c.store.set_nx(lock_key, lock_value, ex=lock_ttl):
        print("Another bot instance is already running. Exiting.", file=sys.stderr)
        return
    lock_refresher = asyncio.create_task(
        _keep_lock_alive(c.store, lock_key, lock_value, lock_ttl)
    )
    # Ensure no leftover webhooks interfere with polling
    await c.bot.delete_webhook(drop_pending_updates=True)
    # Probe for existing long-polling sessions to avoid noisy errors
    try:
        await c.bot.get_updates(limit=1, timeout=0)
    except TelegramConflictError:
        print("Another bot instance is already running. Exiting.", file=sys.stderr)
        await c.store.delete(lock_key)
        return

    # Lightweight web server for Render.com health checks
    async def http_health(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", http_health)
    port = int(os.environ.get("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Middlewares
    ru = json.loads(Path("app/bot/i18n/ru.json").read_text("utf-8"))
    en = json.loads(Path("app/bot/i18n/en.json").read_text("utf-8"))
    c.dp.message.middleware(I18nMiddleware(ru, en))
    c.dp.callback_query.middleware(I18nMiddleware(ru, en))
    c.dp.message.middleware(InjectSessionMiddleware(c.dp["session_factory"]))
    c.dp.callback_query.middleware(InjectSessionMiddleware(c.dp["session_factory"]))
    c.dp.message.middleware(
        InjectDepsMiddleware(
            cfg=c.dp["cfg"], adzuna=c.dp["adzuna"], store=c.dp["store"], settings=c.dp["settings"],
        ),
    )
    c.dp.callback_query.middleware(
        InjectDepsMiddleware(
            cfg=c.dp["cfg"], adzuna=c.dp["adzuna"], store=c.dp["store"], settings=c.dp["settings"],
        ),
    )
    c.dp.message.middleware(RateLimitMiddleware(c.cfg.ratelimit.per_user_per_minute, c.store))

    # Routers
    router = Router()
    # Single-message UX router
    router.include_router(h_anchor.router)
    # Extra handlers for settings, search flow, and card actions
    router.include_router(h_actions.router)
    router.include_router(h_settings.router)
    router.include_router(h_search_params.router)
    # Health endpoint (optional)
    router.include_router(h_health.router)
    c.dp.include_router(router)

    try:
        await c.dp.start_polling(c.bot)
    finally:
        lock_refresher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lock_refresher
        await c.store.delete(lock_key)


if __name__ == "__main__":
    asyncio.run(main())
