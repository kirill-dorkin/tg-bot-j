from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from app.bot.fsm_states import SearchFSM
from app.bot.keyboards import settings_kb
from app.repositories.profiles import ProfilesRepo


router = Router()


@router.message(F.text == "/settings")
async def settings_cmd(m: Message, session, t):
    prof = await ProfilesRepo(session).get(m.from_user.id)
    role = prof.role if prof else "—"
    loc = prof.locations[0] if prof and prof.locations else "—"
    text = (
        f"{t('settings.title')}\n{t('settings.sub')}\n———\n"
        f"Role: {role}\nLocation: {loc}"
    )
    await m.answer(text, reply_markup=settings_kb(t))


@router.callback_query(F.data == "settings:role")
async def settings_set_role(cq: CallbackQuery, state, t):
    await state.set_state(SearchFSM.role)
    await state.update_data(flow="edit_role")
    await cq.message.answer(t("profile.form.role"))
    await cq.answer("")


@router.callback_query(F.data == "settings:location")
async def settings_set_location(cq: CallbackQuery, state, t):
    await state.set_state(SearchFSM.location)
    await state.update_data(flow="edit_location")
    await cq.message.answer(t("profile.form.locations"))
    await cq.answer("")


@router.callback_query(F.data == "settings:reset")
async def settings_reset(cq: CallbackQuery, session, t):
    repo = ProfilesRepo(session)
    await repo.upsert(
        user_id=cq.from_user.id,
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
    await cq.message.answer(t("profile.deleted"))
    await cq.answer("")
