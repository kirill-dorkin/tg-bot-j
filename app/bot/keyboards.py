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


def next_profile_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("buttons.profile.fill"), callback_data="profile:start"),
                InlineKeyboardButton(text=t("buttons.profile.skip"), callback_data="profile:skip"),
            ]
        ]
    )


# -------- Profile inline wizard keyboards --------

# Keep labels minimal and language-aware directly in code for speed.

def _L(lang: str, ru: str, en: str) -> str:
    return ru if lang == "ru" else en


def pf_role_kb(lang: str) -> InlineKeyboardMarkup:
    roles = [
        ("frontend", _L(lang, "Frontend Developer", "Frontend Developer")),
        ("backend", _L(lang, "Backend Developer", "Backend Developer")),
        ("fullstack", _L(lang, "Fullstack Developer", "Fullstack Developer")),
        ("mobile", _L(lang, "Mobile Developer", "Mobile Developer")),
        ("devops", "DevOps"),
        ("data", _L(lang, "Data Engineer", "Data Engineer")),
        ("qa", _L(lang, "QA Engineer", "QA Engineer")),
        ("pm", _L(lang, "Product Manager", "Product Manager")),
        ("design", _L(lang, "Designer", "Designer")),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(roles), 2):
        pair = roles[i : i + 2]
        rows.append([InlineKeyboardButton(text=label, callback_data=f"pf:role:{code}") for code, label in pair])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pf_skills_kb(selected: set[str], lang: str) -> InlineKeyboardMarkup:
    skills = [
        ("react", "React"),
        ("ts", "TypeScript"),
        ("node", "Node.js"),
        ("python", "Python"),
        ("java", "Java"),
        ("go", "Go"),
        ("csharp", "C#"),
        ("php", "PHP"),
        ("kotlin", "Kotlin"),
        ("swift", "Swift"),
        ("cpp", "C++"),
        ("sql", "SQL"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(skills), 2):
        pair = skills[i : i + 2]
        row: list[InlineKeyboardButton] = []
        for code, label in pair:
            picked = "✓ " if code in selected else ""
            row.append(InlineKeyboardButton(text=f"{picked}{label}", callback_data=f"pf:skills:{code}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text=_L(lang, "➡️ Далее", "➡️ Next"), callback_data="pf:skills:next"),
        InlineKeyboardButton(text=_L(lang, "⏭ Пропустить", "⏭ Skip"), callback_data="pf:skills:skip"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pf_locations_kb(selected: set[str], lang: str) -> InlineKeyboardMarkup:
    locs = [
        ("remote", _L(lang, "Remote", "Remote")),
        ("eu", "EU"),
        ("us", "US"),
        ("uk", "UK"),
        ("ru", _L(lang, "Россия", "Russia")),
        ("other", _L(lang, "Другое", "Other")),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(locs), 2):
        pair = locs[i : i + 2]
        row: list[InlineKeyboardButton] = []
        for code, label in pair:
            picked = "✓ " if code in selected else ""
            row.append(InlineKeyboardButton(text=f"{picked}{label}", callback_data=f"pf:loc:{code}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text=_L(lang, "➡️ Далее", "➡️ Next"), callback_data="pf:loc:next"),
        InlineKeyboardButton(text=_L(lang, "⏭ Пропустить", "⏭ Skip"), callback_data="pf:loc:skip"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pf_salary_kb(lang: str) -> InlineKeyboardMarkup:
    # neutral numeric choices, currency-agnostic
    vals = [0, 500, 1000, 1500, 2000, 3000]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(vals), 3):
        chunk = vals[i : i + 3]
        rows.append([InlineKeyboardButton(text=f"💰 {v}", callback_data=f"pf:sal:{v}") for v in chunk])
    rows.append([InlineKeyboardButton(text=_L(lang, "⏭ Пропустить", "⏭ Skip"), callback_data="pf:sal:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pf_formats_kb(selected: set[str], lang: str) -> InlineKeyboardMarkup:
    formats = [
        ("remote", _L(lang, "Удалённо", "Remote")),
        ("hybrid", _L(lang, "Гибрид", "Hybrid")),
        ("onsite", _L(lang, "Офис", "Onsite")),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for code, label in formats:
        picked = "✓ " if code in selected else ""
        row.append(InlineKeyboardButton(text=f"{picked}{label}", callback_data=f"pf:fmt:{code}"))
    rows.append(row)
    rows.append([
        InlineKeyboardButton(text=_L(lang, "➡️ Далее", "➡️ Next"), callback_data="pf:fmt:next"),
        InlineKeyboardButton(text=_L(lang, "⏭ Пропустить", "⏭ Skip"), callback_data="pf:fmt:skip"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pf_experience_kb(lang: str) -> InlineKeyboardMarkup:
    vals = [0, 1, 2, 3, 5, 7, 10]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(vals), 3):
        chunk = vals[i : i + 3]
        rows.append([InlineKeyboardButton(text=f"⌛️ {v}", callback_data=f"pf:exp:{v}") for v in chunk])
    return InlineKeyboardMarkup(inline_keyboard=rows)
