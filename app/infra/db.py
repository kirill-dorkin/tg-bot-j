from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(dsn: str) -> AsyncEngine:
    # Convert psycopg sync DSN to async+psycopg
    if dsn.startswith("postgresql+") and not dsn.startswith("postgresql+psycopg://"):
        # assume already correct
        pass
    async_dsn = dsn.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    # Use asyncpg for performance in async context
    engine = create_async_engine(async_dsn, pool_pre_ping=True)
    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

