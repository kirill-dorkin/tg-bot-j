from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aiogram import Router
from aiogram.enums import ParseMode

from app.bot.handlers import health as h_health
from app.bot import anchor as h_anchor
from app.bot.middlewares import I18nMiddleware, RateLimitMiddleware, InjectSessionMiddleware, InjectDepsMiddleware
from app.container import build_container


async def main() -> None:
    c = await build_container()

    # Middlewares
    ru = json.loads(Path("app/bot/i18n/ru.json").read_text("utf-8"))
    en = json.loads(Path("app/bot/i18n/en.json").read_text("utf-8"))
    c.dp.message.middleware(I18nMiddleware(ru, en))
    c.dp.callback_query.middleware(I18nMiddleware(ru, en))
    c.dp.message.middleware(InjectSessionMiddleware(c.dp["session_factory"]))
    c.dp.callback_query.middleware(InjectSessionMiddleware(c.dp["session_factory"]))
    c.dp.message.middleware(InjectDepsMiddleware(cfg=c.dp["cfg"], adzuna=c.dp["adzuna"], store=c.dp["store"], settings=c.dp["settings"]))
    c.dp.callback_query.middleware(InjectDepsMiddleware(cfg=c.dp["cfg"], adzuna=c.dp["adzuna"], store=c.dp["store"], settings=c.dp["settings"]))
    c.dp.message.middleware(RateLimitMiddleware(c.cfg.ratelimit.per_user_per_minute, c.store))

    # Routers
    router = Router()
    # Single-message UX router
    router.include_router(h_anchor.router)
    # Health endpoint (optional)
    router.include_router(h_health.router)
    c.dp.include_router(router)

    await c.dp.start_polling(c.bot)


if __name__ == "__main__":
    asyncio.run(main())
