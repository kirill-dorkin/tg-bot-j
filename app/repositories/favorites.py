from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import Favorite


class FavoritesRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def add(self, user_id: int, redirect_url: str) -> None:
        fav = await self.s.get(Favorite, {"user_id": user_id, "redirect_url": redirect_url})
        if not fav:
            self.s.add(Favorite(user_id=user_id, redirect_url=redirect_url))

