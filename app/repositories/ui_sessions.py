from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import UiSession


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UiSessionsRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, chat_id: int, user_id: int) -> UiSession | None:
        return await self.s.get(UiSession, (chat_id, user_id))

    async def upsert(self, chat_id: int, user_id: int, *, anchor_message_id: int | None = None, screen_state: str | None = None, payload: dict[str, Any] | None = None) -> UiSession:
        row = await self.s.get(UiSession, (chat_id, user_id))
        if not row:
            row = UiSession(chat_id=chat_id, user_id=user_id, anchor_message_id=anchor_message_id, screen_state=screen_state or "welcome", payload=payload or {}, updated_at=_utcnow())
            self.s.add(row)
        else:
            if anchor_message_id is not None:
                row.anchor_message_id = anchor_message_id
            if screen_state is not None:
                row.screen_state = screen_state
            if payload is not None:
                row.payload = payload
            row.updated_at = _utcnow()
        return row

    async def set_state(self, chat_id: int, user_id: int, *, screen_state: str, payload: dict[str, Any] | None = None) -> None:
        row = await self.s.get(UiSession, (chat_id, user_id))
        if not row:
            row = UiSession(chat_id=chat_id, user_id=user_id, anchor_message_id=None, screen_state=screen_state, payload=payload or {}, updated_at=_utcnow())
            self.s.add(row)
        else:
            row.screen_state = screen_state
            if payload is not None:
                row.payload = payload
            row.updated_at = _utcnow()
