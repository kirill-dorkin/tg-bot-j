from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import Applied


class AppliedRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def mark(self, user_id: int, redirect_url: str, ttl_seconds: int = 300) -> None:
        now = datetime.now(timezone.utc)
        exist = await self.s.get(Applied, {"user_id": user_id, "redirect_url": redirect_url})
        if exist:
            exist.applied_at = now
            exist.expire_at = now + timedelta(seconds=ttl_seconds)
        else:
            self.s.add(
                Applied(
                    user_id=user_id,
                    redirect_url=redirect_url,
                    applied_at=now,
                    expire_at=now + timedelta(seconds=ttl_seconds),
                )
            )

