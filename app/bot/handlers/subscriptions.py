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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Мгновенно" if lang == "ru" else "⚡️ Instant", callback_data="subs:instant"), InlineKeyboardButton(text="🗓 Ежедневно" if lang == "ru" else "🗓 Daily", callback_data="subs:daily"), InlineKeyboardButton(text="📅 Еженедельно" if lang == "ru" else "📅 Weekly", callback_data="subs:weekly")],
        [InlineKeyboardButton(text="🔔 Вкл/Выкл" if lang == "ru" else "🔔 On/Off", callback_data="subs:toggle"), InlineKeyboardButton(text="⏰ Изменить время" if lang == "ru" else "⏰ Change time", callback_data="subs:time")],
    ])
    await m.answer(text, reply_markup=with_lang_row(kb, lang))
