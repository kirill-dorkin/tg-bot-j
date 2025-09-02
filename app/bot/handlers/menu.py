from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.fsm_states import ProfileFSM
from app.bot.keyboards import main_menu_kb, with_lang_row, pf_role_kb


router = Router()


@router.callback_query(F.data == "menu:profile")
async def menu_profile(cq: CallbackQuery, state: FSMContext, t, lang: str):
    # Start inline wizard same as from /start
    await state.update_data(pf={"skills": [], "locations": [], "formats": []})
    text = f"{t('profile.form.title')}\n\n{t('profile.form.role')}"
    await cq.message.edit_text(text, reply_markup=pf_role_kb(lang))
    await cq.answer("")


@router.callback_query(F.data == "menu:subs")
async def menu_subs(cq: CallbackQuery, t, settings, lang: str):
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
    kb = with_lang_row(kb, lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")


@router.callback_query(F.data == "menu:help")
async def menu_help(cq: CallbackQuery, t, lang: str):
    title = t("help.title")
    cmds = t("help.commands")
    src = t("help.source")
    text = f"{title}\n———\n{cmds}\n{src}"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb = with_lang_row(kb, lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")


@router.callback_query(F.data == "menu:settings")
async def menu_settings(cq: CallbackQuery, t, lang: str):
    text = f"{t('settings.title')}\n———"
    kb = with_lang_row(InlineKeyboardMarkup(inline_keyboard=[]), lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")


@router.callback_query(F.data == "menu:fav")
async def menu_favorites(cq: CallbackQuery, t, lang: str):
    text = t("favorites.title").replace("{count}", "0")
    kb = with_lang_row(InlineKeyboardMarkup(inline_keyboard=[]), lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")
