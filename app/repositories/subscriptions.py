from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import Subscription


class SubscriptionsRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def upsert(self, user_id: int, kind: str, schedule_cron: str, enabled: bool) -> None:
        sub = await self.s.get(Subscription, {"user_id": user_id, "kind": kind})
        if not sub:
            sub = Subscription(user_id=user_id, kind=kind)
            self.s.add(sub)
        sub.schedule_cron = schedule_cron
        sub.enabled = enabled

    async def list_enabled(self) -> list[Subscription]:
        res = await self.s.execute(select(Subscription).where(Subscription.enabled == True))  # noqa: E712
        return list(res.scalars().all())

