from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    lang_kb,
    main_menu_kb,
    with_lang_row,
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
    # Show main menu after language selection
    kb = with_lang_row(main_menu_kb(t), lang, t)
    await cq.message.edit_text(f"{t('start.lang_set')}\n\n{t('menu.title')}\n{t('menu.sub')}", reply_markup=kb)


@router.message(F.text == "/menu")
async def menu_cmd(m: Message, t, lang: str):
    kb = with_lang_row(main_menu_kb(t), lang, t)
    text = f"{t('menu.title')}\n{t('menu.sub')}"
    await m.answer(text, reply_markup=kb)



