from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from app.bot.fsm_states import SearchFSM
from app.repositories.profiles import ProfilesRepo


router = Router()


@router.message(F.text == "/settings")
async def settings_cmd(m: Message, session, t):
    prof = await ProfilesRepo(session).get(m.from_user.id)
    role = prof.role if prof else "—"
    loc = prof.locations[0] if prof and prof.locations else "—"
    text = (
        f"{t('settings.title')}\n{t('settings.sub')}\n———\n"
        f"Role: {role}\nLocation: {loc}\n\n"
        "Use /set_role, /set_location or /reset_settings"
    )
    await m.answer(text)


@router.message(F.text == "/set_role")
async def settings_set_role(m: Message, state, t):
    await state.set_state(SearchFSM.role)
    await state.update_data(flow="edit_role")
    await m.answer(t("profile.form.role"))


@router.message(F.text == "/set_location")
async def settings_set_location(m: Message, state, t):
    await state.set_state(SearchFSM.location)
    await state.update_data(flow="edit_location")
    await m.answer(t("profile.form.locations"))


@router.message(F.text == "/reset_settings")
async def settings_reset(m: Message, session, t):
    repo = ProfilesRepo(session)
    await repo.upsert(
        user_id=m.from_user.id,
        role="",
        employment_types=None,
        skills=[],
        locations=[],
        salary_min=0,
        salary_max=None,
        formats=[],
        experience_yrs=0,
    )
    await session.commit()
    await m.answer(t("profile.deleted"))
