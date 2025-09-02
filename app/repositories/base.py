from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.infra.db_models import AuditLog


class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        self.session = self._session_factory()
        try:
            yield self.session
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        finally:
            await self.session.close()
            self.session = None

    async def write_audit(self, action: str, payload: dict, user_id: int | None) -> None:
        if not self.session:
            raise RuntimeError("UoW not started")
        self.session.add(AuditLog(action=action, payload=payload, user_id=user_id))

