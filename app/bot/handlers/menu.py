from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from app.bot.keyboards import with_lang_row
from app.bot.handlers.search import search_start

router = Router()


@router.callback_query(F.data == "menu:quick")
async def menu_quick(
    cq: CallbackQuery,
    session,
    cfg,
    adzuna,
    store,
    t,
    lang: str,
    state: FSMContext,
):
    """Run quick search or launch profile setup if missing."""
    await search_start(cq, session, cfg, adzuna, store, t, lang, state)


@router.callback_query(F.data == "menu:settings")
async def menu_settings(cq: CallbackQuery, t, lang: str):
    text = f"{t('settings.title')}\n———"
    kb = with_lang_row(InlineKeyboardMarkup(inline_keyboard=[]), lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")


@router.callback_query(F.data == "menu:about")
async def menu_about(cq: CallbackQuery, t, lang: str):
    title = t("about.title")
    body = t("about.text")
    text = f"{title}\n———\n{body}"
    kb = with_lang_row(InlineKeyboardMarkup(inline_keyboard=[]), lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")


@router.callback_query(F.data == "menu:support")
async def menu_support(cq: CallbackQuery, t, lang: str):
    text = t("support.text") or "@microstudio_official"
    kb = with_lang_row(InlineKeyboardMarkup(inline_keyboard=[]), lang, t)
    await cq.message.answer(text, reply_markup=kb)
    await cq.answer("")
