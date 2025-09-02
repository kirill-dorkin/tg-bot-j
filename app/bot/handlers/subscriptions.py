from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from app.bot.keyboards import with_lang_row


router = Router()


@router.message(F.text == "/subscribe")
async def subs_cmd(m: Message, t, settings, lang: str):
    # Simple subscriptions screen per spec
    # Timezone read from settings if present, using cfg only for placeholder
    text = t("subs.title").replace("{TZ}", getattr(settings, "TZ", "UTC"))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("buttons.subs.instant"), callback_data="subs:instant"),
                InlineKeyboardButton(text=t("buttons.subs.daily"), callback_data="subs:daily"),
                InlineKeyboardButton(text=t("buttons.subs.weekly"), callback_data="subs:weekly"),
            ],
            [
                InlineKeyboardButton(text=t("buttons.subs.toggle"), callback_data="subs:toggle"),
                InlineKeyboardButton(text=t("buttons.subs.time"), callback_data="subs:time"),
            ],
        ]
    )
    await m.answer(text, reply_markup=with_lang_row(kb, lang, t))
