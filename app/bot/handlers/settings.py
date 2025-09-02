from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup
from app.bot.keyboards import with_lang_row


router = Router()


@router.message(F.text == "/settings")
async def settings_cmd(m: Message, t, lang: str):
    text = f"{t('settings.title')}\n{t('settings.sub')}\n———"
    empty = InlineKeyboardMarkup(inline_keyboard=[])
    await m.answer(text, reply_markup=with_lang_row(empty, lang, t))
