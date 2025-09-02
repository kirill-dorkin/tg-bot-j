from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.fsm_states import ProfileFSM
from app.repositories.profiles import ProfilesRepo


router = Router()


@router.message(ProfileFSM.role)
async def handle_role(m: Message, state: FSMContext, t):
    if not m.text or not m.text.strip():
        await m.answer(t("errors.empty"))
        return
    await state.update_data(role=m.text.strip())
    await state.set_state(ProfileFSM.skills)
    await m.answer(t("profile.form.skills"))


@router.message(ProfileFSM.skills)
async def handle_skills(m: Message, state: FSMContext, t):
    if not m.text or not m.text.strip():
        await m.answer(t("errors.empty"))
        return
    skills = [s.strip() for s in m.text.split(",") if s.strip()]
    await state.update_data(skills=skills)
    await state.set_state(ProfileFSM.locations)
    await m.answer(t("profile.form.locations"))


@router.message(ProfileFSM.locations)
async def handle_locations(m: Message, state: FSMContext, t):
    if not m.text or not m.text.strip():
        await m.answer(t("errors.empty"))
        return
    locs = [s.strip() for s in m.text.split(",") if s.strip()]
    await state.update_data(locations=locs)
    await state.set_state(ProfileFSM.salary_min)
    await m.answer(t("profile.form.salary_min"))


@router.message(ProfileFSM.salary_min)
async def handle_salary_min(m: Message, state: FSMContext, t):
    try:
        val = int(m.text.strip()) if m.text else 0
        if val < 0:
            raise ValueError
    except Exception:
        await m.answer(t("errors.number"))
        return
    await state.update_data(salary_min=val)
    await state.set_state(ProfileFSM.formats)
    await m.answer(t("profile.form.formats"))


@router.message(ProfileFSM.formats)
async def handle_formats(m: Message, state: FSMContext, t):
    if not m.text or not m.text.strip():
        await m.answer(t("errors.empty"))
        return
    formats = [s.strip() for s in m.text.split("/") if s.strip()]
    await state.update_data(formats=formats)
    await state.set_state(ProfileFSM.experience)
    await m.answer(t("profile.form.experience"))


@router.message(ProfileFSM.experience)
async def handle_experience(m: Message, state: FSMContext, session, t):
    try:
        val = int(m.text.strip()) if m.text else 0
        if val < 0:
            raise ValueError
    except Exception:
        await m.answer(t("errors.number"))
        return
    data = await state.get_data()
    repo = ProfilesRepo(session)
    await repo.upsert(
        user_id=m.from_user.id,
        role=data["role"],
        skills=data["skills"],
        locations=data["locations"],
        salary_min=data["salary_min"],
        salary_max=None,
        formats=data["formats"],
        experience_yrs=val,
    )
    await session.commit()
    await state.clear()
    await m.answer(t("profile.saved"))
