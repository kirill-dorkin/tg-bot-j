from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import BlacklistCompany


class BlacklistRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def add(self, user_id: int, company: str) -> None:
        rec = await self.s.get(BlacklistCompany, {"user_id": user_id, "company": company})
        if not rec:
            self.s.add(BlacklistCompany(user_id=user_id, company=company))

