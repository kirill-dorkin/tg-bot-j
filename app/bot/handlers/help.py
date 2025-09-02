from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup
from app.bot.keyboards import with_lang_row


router = Router()


@router.message(F.text == "/help")
async def help_cmd(m: Message, t, lang: str):
    title = t("help.title")
    cmds = t("help.commands")
    src = t("help.source")
    text = f"{title}\n———\n{cmds}\n{src}"
    # RU|EN toggle row only
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb = with_lang_row(kb, lang)
    await m.answer(text, reply_markup=kb)
