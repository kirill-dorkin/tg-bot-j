from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import AppConfig, Settings, load_app_config
from app.infra.db import Base, make_engine, make_session_factory
from app.infra.redis import InMemoryStore, KeyValueStore, RedisStore
from app.infra.dispatcher import Dispatcher
from app.integrations.adzuna_client import AdzunaClient
from app.telemetry.logger import setup_logging


@dataclass
class Container:
    settings: Settings
    cfg: AppConfig
    store: KeyValueStore
    adzuna: AdzunaClient
    bot: Bot
    dp: Dispatcher


async def build_container() -> Container:
    setup_logging()
    settings = Settings()
    cfg = load_app_config(settings.CONFIG_PATH)

    # Redis store
    try:
        store: KeyValueStore = RedisStore(settings.REDIS_URL)
        # ensure connection is alive; fallback to memory if unreachable
        await store.setex("__ping__", 1, "1")
    except Exception:
        store = InMemoryStore()  # graceful degradation

    # DB
    engine = make_engine(settings.POSTGRES_DSN)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", pool_pre_ping=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    session_factory = make_session_factory(engine)

    adzuna = AdzunaClient(settings, cfg)

    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # FSM storage backed by Redis; fallback to in-memory on failure
    try:
        dp_storage = RedisStorage.from_url(settings.REDIS_URL)
        await dp_storage.redis.ping()
    except Exception:
        dp_storage = MemoryStorage()
    dp = Dispatcher(storage=dp_storage)

    # Attach shared context for middlewares/handlers
    dp["settings"] = settings
    dp["cfg"] = cfg
    dp["store"] = store
    dp["session_factory"] = session_factory
    dp["adzuna"] = adzuna

    return Container(settings=settings, cfg=cfg, store=store, adzuna=adzuna, bot=bot, dp=dp)
