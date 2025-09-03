from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from aiohttp import web
from aiogram import Router

from app.bot.handlers import health as h_health
from app.bot import anchor as h_anchor
from app.bot.middlewares import I18nMiddleware, RateLimitMiddleware, InjectSessionMiddleware, InjectDepsMiddleware
from app.container import build_container


async def main() -> None:
    c = await build_container()
    # Acquire a simple distributed lock to avoid running multiple instances
    lock_key = "bot:lock"
    if not await c.store.set_nx(lock_key, str(os.getpid()), ex=60):
        print("Another bot instance is already running. Exiting.", file=sys.stderr)
        return
    # Ensure no leftover webhooks interfere with polling
    await c.bot.delete_webhook(drop_pending_updates=True)

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
    # Health endpoint (optional)
    router.include_router(h_health.router)
    c.dp.include_router(router)

    try:
        await c.dp.start_polling(c.bot)
    finally:
        await c.store.delete(lock_key)


if __name__ == "__main__":
    asyncio.run(main())
