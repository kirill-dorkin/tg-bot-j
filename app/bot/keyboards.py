from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _lang_toggle_row(lang: str, t=None) -> list[InlineKeyboardButton]:
    # Two direct buttons with flags for quick switch
    ru_label = (t("buttons.lang.ru") if t else "🇷🇺 Русский")
    en_label = (t("buttons.lang.en") if t else "🇬🇧 English")
    if lang == "en":
        return [
            InlineKeyboardButton(text=ru_label, callback_data="lang:ru"),
            InlineKeyboardButton(text=en_label, callback_data="lang:en"),
        ]
    return [
        InlineKeyboardButton(text=ru_label, callback_data="lang:ru"),
        InlineKeyboardButton(text=en_label, callback_data="lang:en"),
    ]


def lang_kb(t=None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_lang_toggle_row("ru", t)])


def main_menu_kb(t) -> InlineKeyboardMarkup:
    """Static main menu shown after bot start."""
    labels = t("menu.actions") if callable(getattr(t, "__call__", None)) else []
    if not labels:
        labels = ["1. Быстрый поиск", "2. Настройки", "3. О боте", "4. Поддержка"]
    kb: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=labels[0], callback_data="menu:quick")],
        [InlineKeyboardButton(text=labels[1], callback_data="menu:settings")],
        [InlineKeyboardButton(text=labels[2], callback_data="menu:about")],
        [InlineKeyboardButton(text=labels[3], callback_data="menu:support")],
    ]
    # lang row appended by caller if needed
    return InlineKeyboardMarkup(inline_keyboard=kb)


def card_kb(apply_url: str, shortkey: str, t, lang: str) -> InlineKeyboardMarkup:
    labels = t("card.actions") if callable(getattr(t, "__call__", None)) else ["✅ Откликнуться", "⭐️ Сохранить", "🧭 Похожие", "🙈 Скрыть компанию", "🚩 Пожаловаться"]
    kb: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=labels[0], url=apply_url), InlineKeyboardButton(text=labels[1], callback_data=f"act:save:{shortkey}")],
        [InlineKeyboardButton(text=labels[2], callback_data=f"act:similar:{shortkey}"), InlineKeyboardButton(text=labels[3], callback_data=f"act:hide:{shortkey}")],
        [InlineKeyboardButton(text=labels[4], callback_data=f"act:report:{shortkey}")],
        _lang_toggle_row(lang, t),
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def with_lang_row(markup: InlineKeyboardMarkup, lang: str, t=None) -> InlineKeyboardMarkup:
    rows = list(markup.inline_keyboard)
    rows.append(_lang_toggle_row(lang, t))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Profile wizard keyboards removed as search now collects data sequentially
