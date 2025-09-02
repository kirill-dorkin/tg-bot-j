from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.fsm_states import ProfileFSM
from app.bot.keyboards import (
    lang_kb,
    main_menu_kb,
    next_profile_kb,
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
    # reload t with selected lang
    await cq.message.edit_text(t("start.lang_set"))
    await cq.message.answer(t("start.next_profile"), reply_markup=next_profile_kb(t))


@router.message(F.text == "/menu")
async def menu_cmd(m: Message, t, lang: str):
    kb = with_lang_row(main_menu_kb(t), lang, t)
    await m.answer(t("menu.title"), reply_markup=kb)


@router.callback_query(F.data == "profile:start")
async def profile_start(cq: CallbackQuery, state: FSMContext, t, lang: str):
    # Start inline wizard: keep one message and replace its content per step
    await state.update_data(pf={"skills": [], "locations": [], "formats": []})
    text = f"{t('profile.form.title')}\n\n{t('profile.form.role')}"
    await cq.message.edit_text(text, reply_markup=pf_role_kb(lang))
    await cq.answer("")


@router.callback_query(F.data == "profile:skip")
async def profile_skip(cq: CallbackQuery, t, lang: str):
    kb = with_lang_row(main_menu_kb(t), lang, t)
    await cq.message.edit_text(t("menu.title"), reply_markup=kb)
    await cq.answer("")
