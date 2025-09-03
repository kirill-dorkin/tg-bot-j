from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.repositories.ui_sessions import UiSessionsRepo
from app.repositories.users import UsersRepo
from app.repositories.profiles import ProfilesRepo
from app.repositories.favorites import FavoritesRepo
from app.repositories.applied import AppliedRepo
from app.repositories.shortkeys import ShortKeysRepo
from app.infra.redis import KeyValueStore
from app.config import AppConfig
from app.integrations.adzuna_client import AdzunaClient
from app.domain.models import Profile as DProfile, SearchParams
from app.domain.pipeline import process


router = Router()


def _L(lang: str, ru: str, en: str) -> str:
    return ru if lang == "ru" else en


def _lang_row(lang: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text=_L(lang, "🇷🇺 Русский", "🇷🇺 Russian"), callback_data="lang:set:ru"),
        InlineKeyboardButton(text=_L(lang, "🇬🇧 English", "🇬🇧 English"), callback_data="lang:set:en"),
    ]


def _footer_row(lang: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text=_L(lang, "⬅️ Назад", "⬅️ Back"), callback_data="nav:back"),
        InlineKeyboardButton(text=_L(lang, "🏠 Меню", "🏠 Menu"), callback_data="nav:menu"),
        InlineKeyboardButton(text="🌐 RU | EN", callback_data="lang:toggle"),
    ]


def _field_label(lang: str, field: str) -> str:
    labels = {
        "what": ("что", "what"),
        "where": ("где", "where"),
        "salary_min": ("мин. з/п", "salary_min"),
        "remote": ("удалёнка", "remote"),
        "employment": ("занятость", "employment"),
        "days": ("дней", "days"),
        "skills": ("навыки", "skills"),
    }
    ru, en = labels.get(field, (field, field))
    return ru if lang == "ru" else en


async def _ensure_anchor_and_state(msg: Message, session) -> tuple[int, dict[str, Any]]:
    repo = UiSessionsRepo(session)
    row = await repo.get(msg.chat.id, msg.from_user.id)
    if row and row.anchor_message_id:
        # reuse existing state
        return row.anchor_message_id, {"screen_state": row.screen_state, "payload": row.payload}
    # Create anchor message with welcome content
    lang = "ru"
    welcome = _L(
        lang,
        "👋 Привет! Я помогу быстро найти релевантные вакансии под твой профиль.\n\nЧто внутри:\n• Источник: Adzuna\n• Умные фильтры по навыкам, локации и зарплате\n• Короткие карточки с прямой ссылкой на отклик\n\n🌍 Выбери язык интерфейса:",
        "👋 Hi! I help you quickly find relevant jobs for your profile.\n\nWhat you get:\n• Source: Adzuna\n• Smart filters by skills, location, salary\n• Concise cards with a direct apply link\n\n🌍 Choose interface language:",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[_lang_row(lang)])
    sent = await msg.answer(welcome, reply_markup=kb)
    await repo.upsert(msg.chat.id, msg.from_user.id, anchor_message_id=sent.message_id, screen_state="welcome", payload={})
    await session.commit()
    return sent.message_id, {"screen_state": "welcome", "payload": {}}


async def _edit_anchor(cq_or_msg: CallbackQuery | Message, anchor_id: int, text: str, kb: InlineKeyboardMarkup | None = None):
    # Always edit the anchor; use bot API explicitly in case current message differs
    chat_id = cq_or_msg.message.chat.id if isinstance(cq_or_msg, CallbackQuery) else cq_or_msg.chat.id
    bot = cq_or_msg.bot if isinstance(cq_or_msg, CallbackQuery) else cq_or_msg.bot
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=anchor_id, text=text, reply_markup=kb)
    except TelegramBadRequest as e:
        # Ignore harmless "message is not modified" errors due to idempotent updates
        if "message is not modified" in str(e):
            return
        raise


def _menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=_L(lang, "🔍 Поиск вакансий", "🔍 Job search"), callback_data="menu:search")],
        [InlineKeyboardButton(text=_L(lang, "⚙️ Настроить фильтры", "⚙️ Set filters"), callback_data="menu:profile")],
        [InlineKeyboardButton(text=_L(lang, "ℹ️ О боте", "ℹ️ About bot"), callback_data="menu:about")],
        [InlineKeyboardButton(text=_L(lang, "🆘 Поддержка", "🆘 Support"), callback_data="menu:support")],
        _footer_row(lang),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_menu(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    return _L(lang, "🏠 Главное меню\nВыберите действие.", "🏠 Main menu\nChoose an action."), _menu_keyboard(lang)


@router.message(F.text == "/start")
async def on_start(m: Message, session, t, lang: str):
    anchor_id, state = await _ensure_anchor_and_state(m, session)
    if state["screen_state"] != "welcome":
        # Repaint last state on same anchor
        text, kb = _render_screen(lang, state["screen_state"], state["payload"])
        await _edit_anchor(m, anchor_id, text, kb)
    # else already shows welcome


def _render_welcome(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    txt = _L(
        lang,
        "👋 Привет! Я помогу быстро найти релевантные вакансии под твой профиль.\n\nЧто внутри:\n• Источник: Adzuna\n• Умные фильтры по навыкам, локации и зарплате\n• Короткие карточки с прямой ссылкой на отклик\n\n🌍 Выбери язык интерфейса:",
        "👋 Hi! I help you quickly find relevant jobs for your profile.\n\nWhat you get:\n• Source: Adzuna\n• Smart filters by skills, location, salary\n• Concise cards with a direct apply link\n\n🌍 Choose interface language:",
    )
    return txt, InlineKeyboardMarkup(inline_keyboard=[_lang_row(lang)])


@router.callback_query(F.data.startswith("lang:set:"))
async def on_lang_set(cq: CallbackQuery, session, store: KeyValueStore):
    _, _, target = cq.data.split(":", 2)
    lang = "ru" if target == "ru" else "en"
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    await UsersRepo(session).set_lang(cq.from_user.id, lang)
    # Show saved notice and main menu
    saved = _L(
        lang,
        "✅ Язык сохранён.\n30 секунд — и начнём показывать релевантные вакансии.",
        "✅ Language saved.\nGive me 30 seconds to tailor results to you.",
    )
    menu_text, kb = _render_menu(lang)
    text = f"{saved}\n\n{menu_text}"
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await ui.set_state(cq.message.chat.id, cq.from_user.id, screen_state="menu", payload={})
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "lang:toggle")
async def on_lang_toggle(cq: CallbackQuery, session):
    # Toggle and re-render current screen
    users = UsersRepo(session)
    cur = await users.get_lang(cq.from_user.id)
    new = "en" if cur == "ru" else "ru"
    await users.set_lang(cq.from_user.id, new)
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    text, kb = _render_screen(new, row.screen_state, row.payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


EMPLOYMENT_LABELS = {
    "full": ("Полная занятость", "Full-time"),
    "part": ("Частичная занятость", "Part-time"),
    "contract": ("Контракт", "Contract"),
    "intern": ("Стажировка", "Internship"),
}


def _employment_label(lang: str, code: str) -> str:
    ru, en = EMPLOYMENT_LABELS.get(code, (code, code))
    return ru if lang == "ru" else en


def _render_profile_step(lang: str, step: int, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    if step == 1:
        txt = _L(lang, "👤 Профиль · Шаг 1/4\nВведите имя, как в откликах (можно латиницей).", "👤 Profile · Step 1/4\nEnter your name as used in applications.")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_L(lang, "✏️ Ввести имя", "✏️ Enter name"), callback_data="profile:input:name")],
            _footer_row(lang),
        ])
        name = payload.get("profile", {}).get("name")
        if name:
            txt = _L(lang, f"👤 Профиль · Шаг 1/4\nИмя: {name} ✅", f"👤 Profile · Step 1/4\nName: {name} ✅")
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="profile:next:2")], _footer_row(lang)])
        return txt, kb
    if step == 2:
        txt = _L(lang, "👤 Профиль · Шаг 2/4\nУкажите профессиональную сферу.", "👤 Profile · Step 2/4\nSpecify your professional field.")
        rows: list[list[InlineKeyboardButton]] = []
        tiles = [
            ("IT/Software", "IT/Software"), ("Marketing", "Marketing"), ("Design", "Design"), ("Sales", "Sales"), ("Finance", "Finance"),
        ]
        for i in range(0, len(tiles), 2):
            pair = tiles[i:i+2]
            rows.append([InlineKeyboardButton(text=lbl, callback_data=f"profile:set:industry:{code}") for code, lbl in pair])
        rows.append([InlineKeyboardButton(text=_L(lang, "✏️ Другое", "✏️ Other"), callback_data="profile:input:industry")])
        rows.append(_footer_row(lang))
        industry = payload.get("profile", {}).get("industry")
        if industry:
            txt = _L(lang, f"👤 Профиль · Шаг 2/4\nСфера: {industry} ✅", f"👤 Profile · Step 2/4\nField: {industry} ✅")
            rows = [[InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="profile:next:3")], _footer_row(lang)]
        return txt, InlineKeyboardMarkup(inline_keyboard=rows)
    if step == 3:
        txt = _L(
            lang,
            "👤 Профиль · Шаг 3/4\nВыберите тип занятости (можно несколько) и нажмите Далее, когда закончите.",
            "👤 Profile · Step 3/4\nSelect employment type (multiple allowed) and press Next when done.",
        )
        selected: set[str] = set(payload.get("profile", {}).get("employment", []))

        def mark(code: str) -> str:
            label = _employment_label(lang, code)
            return ("🟩 " if code in selected else "") + label

        rows = [
            [
                InlineKeyboardButton(text=mark("full"), callback_data="profile:toggle:emp:full"),
                InlineKeyboardButton(text=mark("part"), callback_data="profile:toggle:emp:part"),
            ],
            [
                InlineKeyboardButton(text=mark("contract"), callback_data="profile:toggle:emp:contract"),
                InlineKeyboardButton(text=mark("intern"), callback_data="profile:toggle:emp:intern"),
            ],
        ]
        if selected:
            status = ", ".join(_employment_label(lang, s) for s in selected)
            txt = _L(
                lang,
                f"👤 Профиль · Шаг 3/4\nВыбрано: {status}",
                f"👤 Profile · Step 3/4\nSelected: {status}",
            )
            rows.append([InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="profile:next:4")])
        rows.append(_footer_row(lang))
        return txt, InlineKeyboardMarkup(inline_keyboard=rows)
    # step 4 confirm
    p = payload.get("profile", {})
    name = p.get("name", "—")
    industry = p.get("industry", "—")
    et = p.get("employment", [])
    et_disp = ", ".join(_employment_label(lang, e) for e in et) if et else "—"
    txt = _L(lang,
              f"👤 Профиль · Шаг 4/4\nПроверьте данные:\n— Имя: {name}\n— Сфера: {industry}\n— Тип занятости: {et_disp}\n\nСохранить?",
              f"👤 Profile · Step 4/4\nReview details:\n— Name: {name}\n— Field: {industry}\n— Employment: {et_disp}\n\nSave?")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_L(lang, "✅ Сохранить", "✅ Save"), callback_data="profile:save"), InlineKeyboardButton(text=_L(lang, "✏️ Изменить", "✏️ Edit"), callback_data="profile:edit")],
        _footer_row(lang),
    ])
    return txt, kb


def _render_settings_step(lang: str, step: int, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    f = payload.setdefault("filters", {})
    if step == 1:
        txt = _L(
            lang,
            "⚙️ Настройки · Шаг 1/5\nВведите должность или ключевые слова.",
            "⚙️ Settings · Step 1/5\nEnter job title or keywords.",
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=_L(lang, "✏️ Ввести", "✏️ Enter"), callback_data="settings:input:what")],
                _footer_row(lang),
            ]
        )
        if f.get("what"):
            txt = _L(
                lang,
                f"⚙️ Настройки · Шаг 1/5\nДолжность: {f['what']} ✅",
                f"⚙️ Settings · Step 1/5\nRole: {f['what']} ✅",
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="settings:next:2")], _footer_row(lang)]
            )
        return txt, kb
    if step == 2:
        txt = _L(
            lang,
            "⚙️ Настройки · Шаг 2/5\nУкажите локацию поиска.",
            "⚙️ Settings · Step 2/5\nSpecify search location.",
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=_L(lang, "✏️ Ввести", "✏️ Enter"), callback_data="settings:input:where")],
                _footer_row(lang),
            ]
        )
        if f.get("where"):
            txt = _L(
                lang,
                f"⚙️ Настройки · Шаг 2/5\nЛокация: {f['where']} ✅",
                f"⚙️ Settings · Step 2/5\nLocation: {f['where']} ✅",
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="settings:next:3")], _footer_row(lang)]
            )
        return txt, kb
    if step == 3:
        txt = _L(
            lang,
            "⚙️ Настройки · Шаг 3/5\nУкажите минимальную зарплату.",
            "⚙️ Settings · Step 3/5\nSet minimum salary.",
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=_L(lang, "✏️ Ввести", "✏️ Enter"), callback_data="settings:input:salary_min")],
                _footer_row(lang),
            ]
        )
        if f.get("salary_min"):
            txt = _L(
                lang,
                f"⚙️ Настройки · Шаг 3/5\nМин. з/п: {f['salary_min']} ✅",
                f"⚙️ Settings · Step 3/5\nMin salary: {f['salary_min']} ✅",
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="settings:next:4")], _footer_row(lang)]
            )
        return txt, kb
    if step == 4:
        remote = bool(f.get("remote"))
        txt = _L(
            lang,
            "⚙️ Настройки · Шаг 4/5\nРазрешить удалённую работу?",
            "⚙️ Settings · Step 4/5\nAllow remote work?",
        )
        rows = [
            [
                InlineKeyboardButton(
                    text=_L(lang, "Удалёнка: да" if remote else "Удалёнка: нет", "Remote: on" if remote else "Remote: off"),
                    callback_data="settings:toggle:remote",
                )
            ],
            [InlineKeyboardButton(text=_L(lang, "Далее →", "Next →"), callback_data="settings:next:5")],
            _footer_row(lang),
        ]
        return txt, InlineKeyboardMarkup(inline_keyboard=rows)
    # step 5 confirm
    what = f.get("what", "—")
    where = f.get("where", "—")
    salary = f.get("salary_min", "—")
    remote = _L(lang, "да" if f.get("remote") else "нет", "yes" if f.get("remote") else "no")
    txt = _L(
        lang,
        f"⚙️ Настройки · Шаг 5/5\nПроверьте данные:\n— Что: {what}\n— Где: {where}\n— Мин. з/п: {salary}\n— Удалённо: {remote}\n\nСохранить?",
        f"⚙️ Settings · Step 5/5\nReview details:\n— What: {what}\n— Where: {where}\n— Min salary: {salary}\n— Remote: {remote}\n\nSave?",
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_L(lang, "✅ Сохранить", "✅ Save"), callback_data="settings:save"),
                InlineKeyboardButton(text=_L(lang, "✏️ Изменить", "✏️ Edit"), callback_data="settings:edit"),
            ],
            _footer_row(lang),
        ]
    )
    return txt, kb


def _render_filters(lang: str, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    f = payload.get("filters", {})
    what = f.get("what") or "-"
    where = f.get("where") or "-"
    salary_min = f.get("salary_min") or "-"
    remote_flag = f.get("remote", False)
    remote = "☑" if remote_flag else "☐"
    employment_codes = f.get("employment", [])
    employment_ru = ",".join(_employment_label("ru", e) for e in employment_codes) or "-"
    employment_en = ",".join(_employment_label("en", e) for e in employment_codes) or "-"
    days = f.get("days") or "7"
    header = _L(lang, "🔍 Поиск\nУточните фильтры или запустите сразу.", "🔍 Search\nAdjust filters or start now.")
    state_line_ru = (
        f"{_field_label('ru','what')}: \"{what}\" | "
        f"{_field_label('ru','where')}: \"{where}\" | "
        f"{_field_label('ru','salary_min')}: {salary_min} | "
        f"{_field_label('ru','remote')}: {'да' if remote_flag else 'нет'} | "
        f"{_field_label('ru','employment')}: {employment_ru} | "
        f"{_field_label('ru','days')}: {days}"
    )
    state_line_en = (
        f"{_field_label('en','what')}: \"{what}\" | "
        f"{_field_label('en','where')}: \"{where}\" | "
        f"{_field_label('en','salary_min')}: {salary_min} | "
        f"{_field_label('en','remote')}: {remote_flag} | "
        f"{_field_label('en','employment')}: {employment_en} | "
        f"{_field_label('en','days')}: {days}"
    )
    state_line = _L(lang, state_line_ru, state_line_en)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=f"✏️ {_field_label(lang,'what')}", callback_data="filters:edit:what"),
            InlineKeyboardButton(text=f"📍 {_field_label(lang,'where')}", callback_data="filters:edit:where"),
        ],
        [
            InlineKeyboardButton(text=f"💰 {_field_label(lang,'salary_min')}", callback_data="filters:edit:salary_min"),
            InlineKeyboardButton(text=f"🏠 {_field_label(lang,'remote')} {remote}", callback_data="filters:toggle:remote"),
        ],
        [
            InlineKeyboardButton(text=f"🧩 {_field_label(lang,'skills')}", callback_data="filters:edit:skills"),
            InlineKeyboardButton(text=f"🗓 {_field_label(lang,'days')}", callback_data="filters:edit:days"),
        ],
        [
            InlineKeyboardButton(text=_L(lang, "▶️ Показать", "▶️ Show"), callback_data="search:show"),
            InlineKeyboardButton(text=_L(lang, "♻️ Сброс", "♻️ Reset"), callback_data="filters:reset"),
        ],
        _footer_row(lang),
    ]
    return f"{header}\n{state_line}", InlineKeyboardMarkup(inline_keyboard=rows)


def _render_card(lang: str, card: dict[str, str], payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    # Card text
    title = card.get("title", "")
    parts = [p.strip() for p in (card.get("subtitle", "").split("•") if card.get("subtitle") else [])]
    city = parts[0] if len(parts) > 0 else _L(lang, "—", "—")
    salary = parts[1] if len(parts) > 1 else ""
    if not salary or salary == "З/п не указана":
        salary = _L(lang, "З/п не указана", "Not specified")
    posted_raw = parts[2] if len(parts) > 2 else ""
    if posted_raw == "сегодня":
        posted = _L(lang, "сегодня", "today")
    elif posted_raw == "вчера":
        posted = _L(lang, "вчера", "yesterday")
    elif posted_raw.endswith(" дн. назад"):
        days = posted_raw.split()[0]
        posted = _L(lang, f"{days} дн. назад", f"{days}d ago")
    else:
        posted = posted_raw or _L(lang, "—", "—")
    summary = card.get("summary", "")
    text = f"💼 {title}\n📍 {city}   💰 {salary}   ⏱ {posted}\n🧩 {summary}"
    # Actions
    applied_urls: set[str] = set(payload.get("applied_urls", []))
    first_btn = InlineKeyboardButton(text=_L(lang, "✅ Откликнуться", "✅ Apply"), callback_data=f"card:apply")
    if card.get("apply_url") and card["apply_url"] in applied_urls:
        first_btn = InlineKeyboardButton(text=_L(lang, "🔗 Перейти к отклику", "🔗 Open apply"), url=card["apply_url"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [first_btn, InlineKeyboardButton(text=_L(lang, "⭐ Сохранить", "⭐ Save"), callback_data="card:save")],
        [InlineKeyboardButton(text=_L(lang, "🙈 Скрыть компанию", "🙈 Hide company"), callback_data="card:hide"), InlineKeyboardButton(text=_L(lang, "🧭 Похожие", "🧭 Similar"), callback_data="card:similar")],
        [InlineKeyboardButton(text=_L(lang, "◀️ Пред", "◀️ Prev"), callback_data="card:prev"), InlineKeyboardButton(text=_L(lang, "▶️ След", "▶️ Next"), callback_data="card:next"), InlineKeyboardButton(text=_L(lang, "📊 Сводка", "📊 Summary"), callback_data="card:summary")],
        _footer_row(lang),
    ])
    return text, kb


def _render_screen(lang: str, state: str, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    if state == "welcome":
        return _render_welcome(lang)
    if state == "menu":
        return _render_menu(lang)
    if state == "profile_step_1":
        return _render_profile_step(lang, 1, payload)
    if state == "profile_step_2":
        return _render_profile_step(lang, 2, payload)
    if state == "profile_step_3":
        return _render_profile_step(lang, 3, payload)
    if state == "profile_step_4":
        return _render_profile_step(lang, 4, payload)
    if state.startswith("settings_step_"):
        step = int(state.split("_")[-1])
        return _render_settings_step(lang, step, payload)
    if state == "search_filters":
        return _render_filters(lang, payload)
    if state == "search_card":
        cards = payload.get("cards", [])
        idx = int(payload.get("cursor", 0))
        if not cards:
            empty = _L(lang, "😕 Подходящих вакансий нет. Попробуйте снять часть фильтров или разрешить Remote.", "😕 No matching jobs. Try relaxing filters or enabling Remote.")
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_L(lang, "🧹 Сброс фильтров", "🧹 Reset filters"), callback_data="filters:reset")], [InlineKeyboardButton(text=_L(lang, "🌐 Remote: Вкл", "🌐 Remote: On"), callback_data="filters:force_remote")], _footer_row(lang)])
            return empty, kb
        return _render_card(lang, cards[idx], payload)
    if state == "about":
        txt = _L(lang,
                 "ℹ️ О боте\nЯ показываю вакансии из Adzuna, убираю шум и сортирую по релевантности. Профиль и фильтры можно менять в любой момент. Ничего лишнего — сразу ссылка на отклик.",
                 "ℹ️ About\nI fetch jobs from Adzuna, remove noise, and rank results by relevance. Update your profile and filters anytime. No fluff — direct apply link.")
        return txt, InlineKeyboardMarkup(inline_keyboard=[_footer_row(lang)])
    if state == "support":
        txt = _L(lang, "🆘 Поддержка\nОпишите вопрос одной строкой или откройте чат поддержки.", "🆘 Support\nDescribe your issue briefly or open support chat.")
        rows = [
            [InlineKeyboardButton(text=_L(lang, "💬 Открыть чат", "💬 Open chat"), url="https://t.me/") , InlineKeyboardButton(text=_L(lang, "✉️ Email", "✉️ Email"), url="mailto:support@example.com")],
            _footer_row(lang),
        ]
        return txt, InlineKeyboardMarkup(inline_keyboard=rows)
    # fallback to menu
    return _render_menu(lang)


# Navigation
@router.callback_query(F.data == "nav:menu")
async def nav_menu(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="menu")
    text, kb = _render_menu(lang)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "nav:back")
async def nav_back(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    state = row.screen_state
    payload = row.payload or {}
    back_map = {
        "profile_step_2": "profile_step_1",
        "profile_step_3": "profile_step_2",
        "profile_step_4": "profile_step_3",
        "settings_step_1": "menu",
        "settings_step_2": "settings_step_1",
        "settings_step_3": "settings_step_2",
        "settings_step_4": "settings_step_3",
        "settings_step_5": "settings_step_4",
        "search_filters": "menu",
        "search_card": "search_filters",
        "about": "menu",
        "support": "menu",
        "welcome": "welcome",
    }
    new_state = back_map.get(state, "menu")
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=new_state, payload=payload)
    text, kb = _render_screen(lang, new_state, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "menu:about")
async def menu_about(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="about")
    text, kb = _render_screen(lang, "about", {})
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "menu:support")
async def menu_support(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="support")
    text, kb = _render_screen(lang, "support", {})
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "menu:settings")
async def menu_settings(cq: CallbackQuery, session, t, lang: str):
    # Prefill filters from profile data when available
    prof = await ProfilesRepo(session).get(cq.from_user.id)
    filters = {
        "what": (prof.role if prof and prof.role else None),
        "where": (prof.locations[0] if prof and prof.locations else None),
        "salary_min": (prof.salary_min if prof and prof.salary_min else None),
        "remote": bool(
            prof
            and (
                (prof.formats and ("remote" in prof.formats))
                or (prof.locations and any(l.lower() == "remote" for l in prof.locations))
            )
        ),
    }
    payload = {"filters": filters}
    ui = UiSessionsRepo(session)
    row = await ui.upsert(
        cq.message.chat.id, cq.from_user.id, screen_state="settings_step_1", payload=payload
    )
    text, kb = _render_settings_step(lang, 1, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data.startswith("settings:next:"))
async def settings_next(cq: CallbackQuery, session, t, lang: str):
    step = int(cq.data.split(":")[2])
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=f"settings_step_{step}", payload=payload)
    text, kb = _render_settings_step(lang, step, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data.startswith("settings:input:"))
async def settings_input(cq: CallbackQuery, session, t, lang: str):
    field = cq.data.split(":")[2]
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    payload["input_mode"] = f"settings:{field}"
    await ui.upsert(cq.message.chat.id, cq.from_user.id, payload=payload)
    await session.commit()
    hints = {
        "what": _L(lang, "Введите должность или ключевые слова", "Enter job title or keywords"),
        "where": _L(lang, "Укажите локацию", "Specify location"),
        "salary_min": _L(lang, "Введите минимальную зарплату", "Enter minimum salary"),
    }
    step = int(row.screen_state.split("_")[-1]) if row.screen_state and row.screen_state.startswith("settings_step_") else 1
    text, kb = _render_settings_step(lang, step, payload)
    text = f"{text}\n\n{hints.get(field, '')}"
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "settings:toggle:remote")
async def settings_toggle_remote(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    f = payload.setdefault("filters", {})
    f["remote"] = not bool(f.get("remote"))
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="settings_step_4", payload=payload)
    text, kb = _render_settings_step(lang, 4, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data.in_({"settings:save", "settings:edit"}))
async def settings_finalize(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    if cq.data == "settings:edit":
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="settings_step_1", payload=payload)
        text, kb = _render_settings_step(lang, 1, payload)
    else:
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="menu", payload=payload)
        text, kb = _render_menu(lang)
        text = _L(lang, "✅ Настройки сохранены.\n\n" + text, "✅ Settings saved.\n\n" + text)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data.in_({"menu:search", "search:quick"}))
async def search_direct(cq: CallbackQuery, session, cfg: AppConfig, adzuna: AdzunaClient, store: KeyValueStore, t, lang: str):
    await search_show(cq, session, cfg, adzuna, store, t, lang)


# Filters interactions
@router.callback_query(F.data.startswith("filters:toggle:"))
async def filters_toggle(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    f = payload.setdefault("filters", {})
    _, _, field = cq.data.split(":", 2)
    if field == "remote":
        f["remote"] = not bool(f.get("remote"))
    if field == "force_remote":
        f["remote"] = True
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_filters", payload=payload)
    text, kb = _render_filters(lang, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "filters:reset")
async def filters_reset(cq: CallbackQuery, session, t, lang: str):
    payload = {"filters": {"days": 7, "remote": False, "employment": []}}
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_filters", payload=payload)
    text, kb = _render_filters(lang, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


# Micro-form inputs: set input mode in payload and wait for text messages
@router.callback_query(F.data.startswith("filters:edit:"))
async def filters_edit(cq: CallbackQuery, session, t, lang: str):
    field = cq.data.split(":")[2]
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    payload["input_mode"] = f"filters:{field}"
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_filters", payload=payload)
    # Commit before prompting to avoid losing input if user replies quickly
    await session.commit()
    if field == "what":
        hint = _L(
            lang,
            "Введите должность или ключевые слова, например: Python разработчик",
            "Enter job title or keywords, e.g., Python developer",
        )
    else:
        hint = _L(
            lang,
            f"Введите значение для {_field_label('ru', field)}",
            f"Enter value for {_field_label('en', field)}",
        )
    text, kb = _render_filters(lang, payload)
    text = f"{text}\n\n{hint}"
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.message()
async def on_free_text(m: Message, session, t, lang: str):
    # Capture text if input_mode is set
    ui = UiSessionsRepo(session)
    row = await ui.upsert(m.chat.id, m.from_user.id)
    anchor_id = row.anchor_message_id
    if not anchor_id:
        anchor_id, _ = await _ensure_anchor_and_state(m, session)
        row.anchor_message_id = anchor_id
    payload = (row.payload or {})
    input_mode = payload.get("input_mode")
    if not input_mode:
        return
    bot = m.bot
    if input_mode.startswith("filters:"):
        _, field = input_mode.split(":", 1)
        f = payload.setdefault("filters", {})
        if field == "salary_min" or field == "days":
            try:
                f[field] = int(m.text.strip())
            except Exception:
                pass
        else:
            f[field] = m.text.strip()
        payload.pop("input_mode", None)
        state = "search_filters"
        text, kb = _render_filters(lang, payload)
    elif input_mode.startswith("settings:"):
        _, field = input_mode.split(":", 1)
        f = payload.setdefault("filters", {})
        if field == "salary_min":
            try:
                f[field] = int(m.text.strip())
            except Exception:
                pass
        else:
            f[field] = m.text.strip()
        payload.pop("input_mode", None)
        cur_step = 1
        if row.screen_state and row.screen_state.startswith("settings_step_"):
            try:
                cur_step = int(row.screen_state.split("_")[-1])
            except Exception:
                cur_step = 1
        next_step = min(cur_step + 1, 5)
        state = f"settings_step_{next_step}"
        text, kb = _render_settings_step(lang, next_step, payload)
    elif input_mode == "profile:name":
        if not m.text or not m.text.strip():
            await m.answer(_L(lang, "Имя не должно быть пустым. Введите имя (можно латиницей) и отправьте его сообщением.", "Name cannot be empty. Enter your name and send it as a message."))
            return
        p = payload.setdefault("profile", {})
        p["name"] = m.text.strip()
        payload.pop("input_mode", None)
        state = "profile_step_2"
        text, kb = _render_profile_step(lang, 2, payload)
    elif input_mode == "profile:industry":
        if not m.text or not m.text.strip():
            await m.answer(_L(lang, "Сфера не должна быть пустой. Укажите профессиональную сферу.", "Field cannot be empty. Specify your professional field."))
            return
        p = payload.setdefault("profile", {})
        p["industry"] = m.text.strip()
        payload.pop("input_mode", None)
        state = "profile_step_3"
        text, kb = _render_profile_step(lang, 3, payload)
    else:
        return

    # Clear chat: remove user message and previous anchor
    try:
        await m.delete()
    except Exception:
        pass
    if anchor_id:
        try:
            await bot.delete_message(m.chat.id, anchor_id)
        except Exception:
            pass

    sent = await bot.send_message(m.chat.id, text, reply_markup=kb)
    await ui.upsert(m.chat.id, m.from_user.id, screen_state=state, payload=payload, anchor_message_id=sent.message_id)
    await session.commit()
    return

@router.callback_query(F.data.startswith("profile:"))
async def profile_actions(cq: CallbackQuery, session, t, lang: str):
    parts = cq.data.split(":")
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {}
    p = payload.setdefault("profile", {})
    if parts[1] == "input" and parts[2] == "name":
        payload["input_mode"] = "profile:name"
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="profile_step_1", payload=payload)
        # Commit early so text input after prompt is captured reliably
        await session.commit()
        text, kb = _render_profile_step(lang, 1, payload)
        text += "\n\n" + _L(lang, "Введите имя (можно латиницей) и отправьте его сообщением.", "Enter your name and send it as a message.")
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    elif parts[1] == "set" and parts[2] == "industry":
        p["industry"] = parts[3]
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="profile_step_2", payload=payload)
        text, kb = _render_profile_step(lang, 2, payload)
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    elif parts[1] == "input" and parts[2] == "industry":
        payload["input_mode"] = "profile:industry"
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="profile_step_2", payload=payload)
        await session.commit()
        text, kb = _render_profile_step(lang, 2, payload)
        text += "\n\n" + _L(lang, "Укажите профессиональную сферу и отправьте её сообщением.", "Specify your professional field and send it as a message.")
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    elif parts[1] == "toggle" and parts[2] == "emp":
        code = parts[3]
        sel = set(p.get("employment", []))
        if code in sel:
            sel.remove(code)
        else:
            sel.add(code)
        p["employment"] = list(sel)
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="profile_step_3", payload=payload)
        text, kb = _render_profile_step(lang, 3, payload)
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    elif parts[1] == "next":
        step = int(parts[2])
        st = f"profile_step_{step}"
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=st, payload=payload)
        text, kb = _render_profile_step(lang, step, payload)
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    elif parts[1] == "save":
        # Persist profile
        name = p.get("name") or ""
        industry = p.get("industry") or ""
        employment = p.get("employment", [])
        await UsersRepo(session).set_full_name(cq.from_user.id, name)
        await ProfilesRepo(session).upsert(
            user_id=cq.from_user.id,
            role=industry,
            employment_types=employment,
            skills=[], locations=[], salary_min=0, salary_max=None, formats=[], experience_yrs=0,
        )
        # Clear temp and go to menu
        payload.pop("profile", None)
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="menu", payload=payload)
        text, kb = _render_menu(lang)
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, _L(lang, "✅ Профиль сохранён.\n\n" + text, "✅ Profile saved.\n\n" + text), kb)
    elif parts[1] == "edit":
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="profile_step_1", payload=payload)
        text, kb = _render_profile_step(lang, 1, payload)
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "menu:profile")
async def menu_profile(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="profile_step_1", payload={"profile": {}})
    text, kb = _render_profile_step(lang, 1, row.payload or {})
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "search:show")
async def search_show(cq: CallbackQuery, session, cfg: AppConfig, adzuna: AdzunaClient, store: KeyValueStore, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    # Simple progress animation
    anchor_id = row.anchor_message_id or cq.message.message_id
    for step in ["⏳", "⏳.", "⏳.."]:
        await _edit_anchor(cq, anchor_id, step)
        await asyncio.sleep(0.3)
    # Run search
    prof = await ProfilesRepo(session).get(cq.from_user.id)
    profile = DProfile(
        role=(payload.get("filters", {}).get("what") or (prof.role if prof else "")),
        skills=prof.skills if prof and prof.skills else [],
        locations=prof.locations if prof and prof.locations else [],
        salary_min=int(payload.get("filters", {}).get("salary_min") or (prof.salary_min if prof else 0) or 0),
        salary_max=prof.salary_max if prof else None,
        formats=prof.formats if prof and prof.formats else [],
        experience_yrs=prof.experience_yrs if prof and prof.experience_yrs else 0,
    )
    params = SearchParams(max_days_old=int(payload.get("filters", {}).get("days") or cfg.search.max_days_old_default), sort="relevance")
    try:
        results = await adzuna.search("gb", 1, cfg.search.results_per_page, what=profile.role or None, where=(payload.get("filters", {}).get("where") or None), sort=params.sort, max_days_old=params.max_days_old)
    except Exception:
        results = []
    pr = process(results, profile, params, cfg)
    cards = pr["cards"][:5]
    payload["cards"] = cards
    payload["cursor"] = 0
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_card", payload=payload)
    text, kb = _render_screen(lang, "search_card", payload)
    await _edit_anchor(cq, anchor_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data.in_({"card:next", "card:prev", "card:summary"}))
async def card_nav(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {}
    cards = payload.get("cards", [])
    idx = int(payload.get("cursor", 0))
    if cq.data == "card:next" and cards:
        idx = min(idx + 1, len(cards) - 1)
    elif cq.data == "card:prev" and cards:
        idx = max(idx - 1, 0)
    elif cq.data == "card:summary":
        shown = len(cards)
        text = _L(lang, f"📊 Результаты\nПоказано: {shown} из {shown}\nФильтры: кратко", f"📊 Results\nShown: {shown} of {shown}\nFilters: short")
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, InlineKeyboardMarkup(inline_keyboard=[_footer_row(lang)]))
        await session.commit()
        await cq.answer("")
        return
    payload["cursor"] = idx
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_card", payload=payload)
    text, kb = _render_screen(lang, "search_card", payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data.in_({"card:apply", "card:save", "card:hide", "card:similar"}))
async def card_actions(cq: CallbackQuery, session, store: KeyValueStore, t, lang: str):
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {}
    cards = payload.get("cards", [])
    idx = int(payload.get("cursor", 0))
    card = cards[idx] if 0 <= idx < len(cards) else None
    if not card:
        await cq.answer("")
        return
    url = card.get("apply_url")
    if cq.data == "card:apply" and url:
        ok = await store.set_nx(f"idemp:apply:{cq.from_user.id}|{url}", "1", ex=300)
        if ok:
            await AppliedRepo(session).mark(cq.from_user.id, url)
            await session.commit()
        # Mark applied in payload to swap button to URL
        applied = set(payload.get("applied_urls", []))
        applied.add(url)
        payload["applied_urls"] = list(applied)
        await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_card", payload=payload)
        text, kb = _render_screen(lang, "search_card", payload)
        await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
        await session.commit()
        await cq.answer(_L(lang, "Готово", "Done"))
    elif cq.data == "card:save" and url:
        await FavoritesRepo(session).add(cq.from_user.id, url)
        await session.commit()
        await cq.answer(_L(lang, "⭐ Сохранено", "⭐ Saved"))
    elif cq.data == "card:hide":
        await cq.answer(_L(lang, "🙈 Скрыто", "🙈 Hidden"))
    elif cq.data == "card:similar":
        await cq.answer(_L(lang, "🧭 Похожие (демо)", "🧭 Similar (demo)"))
