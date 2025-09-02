from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db_models import Profile as DBProfile


class ProfilesRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def upsert(
        self,
        user_id: int,
        *,
        role: str,
        employment_types: list[str] | None = None,
        skills: list[str],
        locations: list[str],
        salary_min: int,
        salary_max: int | None,
        formats: list[str],
        experience_yrs: int,
    ) -> None:
        prof = await self.s.get(DBProfile, user_id)
        if not prof:
            prof = DBProfile(user_id=user_id)
            self.s.add(prof)
        prof.role = role
        prof.employment_types = employment_types
        prof.skills = skills
        prof.locations = locations
        prof.salary_min = salary_min
        prof.salary_max = salary_max
        prof.formats = formats
        prof.experience_yrs = experience_yrs

    async def get(self, user_id: int) -> DBProfile | None:
        return await self.s.get(DBProfile, user_id)
