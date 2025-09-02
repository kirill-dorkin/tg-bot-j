from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import User


class UsersRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def upsert(self, user_id: int, lang: str, full_name: str | None = None) -> None:
        user = await self.s.get(User, user_id)
        if user:
            user.lang = lang
            if full_name is not None:
                user.full_name = full_name
        else:
            self.s.add(User(id=user_id, lang=lang, full_name=full_name))

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.upsert(user_id, lang)

    async def get_lang(self, user_id: int) -> str | None:
        user = await self.s.get(User, user_id)
        return user.lang if user else None

    async def set_full_name(self, user_id: int, full_name: str) -> None:
        user = await self.s.get(User, user_id)
        if user:
            user.full_name = full_name
        else:
            self.s.add(User(id=user_id, lang="ru", full_name=full_name))
