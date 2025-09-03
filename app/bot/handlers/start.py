from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    lang_kb,
    main_menu_kb,
    with_lang_row,
    pf_role_kb,
)
from app.repositories.users import UsersRepo


router = Router()


@router.message(F.text == "/start")
async def start_cmd(m: Message, t):
    await m.answer(t("start.welcome"), reply_markup=lang_kb(t))


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(cq: CallbackQuery, t, session, state: FSMContext):
    lang = cq.data.split(":")[1]
    await UsersRepo(session).set_lang(cq.from_user.id, lang)
    await session.commit()
    # Start profile setup immediately with selected language
    await profile_start(cq, state, t, lang, t("start.lang_set"))


@router.message(F.text == "/menu")
async def menu_cmd(m: Message, t, lang: str):
    kb = with_lang_row(main_menu_kb(t), lang, t)
    text = f"{t('menu.title')}\n{t('menu.sub')}"
    await m.answer(text, reply_markup=kb)


@router.callback_query(F.data == "profile:start")
async def profile_start(
    cq: CallbackQuery,
    state: FSMContext,
    t,
    lang: str,
    alert: str | None = None,
):
    """Start inline profile setup wizard."""
    await state.update_data(pf={"skills": [], "locations": [], "formats": []})
    text = f"{t('profile.form.title')}\n\n{t('profile.form.role')}"
    await cq.message.edit_text(text, reply_markup=pf_role_kb(lang))
    await cq.answer(alert or "")

