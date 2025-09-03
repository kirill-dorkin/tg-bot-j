from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.repositories.ui_sessions import UiSessionsRepo
from app.repositories.users import UsersRepo
from app.repositories.favorites import FavoritesRepo
from app.repositories.applied import AppliedRepo
from app.repositories.shortkeys import ShortKeysRepo
from app.infra.redis import KeyValueStore
from app.config import AppConfig
from app.integrations.adzuna_client import AdzunaClient
from app.domain.models import Profile as DProfile, SearchParams
from httpx import HTTPStatusError
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
        [InlineKeyboardButton(text=_L(lang, "⚙️ Настройки", "⚙️ Settings"), callback_data="menu:settings")],
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
    # Show saved + menu
    saved = _L(lang, "✅ Язык сохранён.\n30 секунд — и начнём показывать релевантные вакансии.", "✅ Language saved.\nGive me 30 seconds to tailor results to you.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_L(lang, "🚀 Быстрый поиск", "🚀 Quick search"), callback_data="search:quick")],
        [InlineKeyboardButton(text=_L(lang, "⚙️ Настройки", "⚙️ Settings"), callback_data="menu:settings")],
        [InlineKeyboardButton(text=_L(lang, "ℹ️ О боте", "ℹ️ About"), callback_data="menu:about")],
        _footer_row(lang),
    ])
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, saved, kb)
    await ui.set_state(cq.message.chat.id, cq.from_user.id, screen_state="post_lang", payload={})
    await session.commit()
    await cq.answer("")


def _render_settings(lang: str, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    f = payload.get('filters', {})
    what = f.get('what') or '-'
    where = f.get('where') or '-'
    salary_min = f.get('salary_min') or '-'
    rows = [
        [InlineKeyboardButton(text='✏️ what', callback_data='filters:edit:what'), InlineKeyboardButton(text='📍 where', callback_data='filters:edit:where')],
        [InlineKeyboardButton(text='💰 salary_min', callback_data='filters:edit:salary_min'), InlineKeyboardButton(text='♻️ reset', callback_data='filters:reset')],
        _footer_row(lang),
    ]
    txt = _L(lang, '⚙️ Настройки поиска', '⚙️ Search settings') + f"\nwhat: {what} | where: {where} | salary_min: {salary_min}"
    return txt, InlineKeyboardMarkup(inline_keyboard=rows)


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




def _render_filters(lang: str, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    f = payload.get("filters", {})
    what = f.get("what") or "-"
    where = f.get("where") or "-"
    salary_min = f.get("salary_min") or "-"
    remote = "☑" if f.get("remote") else "☐"
    employment = ",".join(f.get("employment", [])) or "-"
    days = f.get("days") or "7"
    header = _L(lang, "🔍 Поиск\nУточните фильтры или запустите сразу.", "🔍 Search\nAdjust filters or start now.")
    state_line = f"what: \"{what}\" | where: \"{where}\" | salary_min: {salary_min} | remote: {f.get('remote', False)} | type: {employment} | days: {days}"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✏️ what", callback_data="filters:edit:what"), InlineKeyboardButton(text="📍 where", callback_data="filters:edit:where")],
        [InlineKeyboardButton(text="💰 salary_min", callback_data="filters:edit:salary_min"), InlineKeyboardButton(text=f"🏠 remote {remote}", callback_data="filters:toggle:remote")],
        [InlineKeyboardButton(text="🧩 skills", callback_data="filters:edit:skills"), InlineKeyboardButton(text="🗓 days", callback_data="filters:edit:days")],
        [InlineKeyboardButton(text=_L(lang, "▶️ Показать", "▶️ Show"), callback_data="search:show"), InlineKeyboardButton(text=_L(lang, "♻️ Сброс", "♻️ Reset"), callback_data="filters:reset")],
        _footer_row(lang),
    ]
    return f"{header}\n{state_line}", InlineKeyboardMarkup(inline_keyboard=rows)


def _render_card(lang: str, card: dict[str, str], payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    # Card text
    title = card.get("title", "")
    parts = [p.strip() for p in (card.get("subtitle", "").split("•") if card.get("subtitle") else [])]
    city = parts[0] if len(parts) > 0 else _L(lang, "—", "—")
    salary = parts[1] if len(parts) > 1 else _L(lang, "З/п не указана", "Not specified")
    posted = parts[2] if len(parts) > 2 else _L(lang, "—", "—")
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
    if state == "settings":
        return _render_settings(lang, payload)
    if state == "search_filters":
        return _render_filters(lang, payload)
    if state == "search_card":
        cards = payload.get("cards", [])
        idx = int(payload.get("cursor", 0))
        if not cards:
            msg = payload.get("error") or _L(lang, "😕 Подходящих вакансий нет. Попробуйте снять часть фильтров или разрешить Remote.", "😕 No matching jobs. Try relaxing filters or enabling Remote.")
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_L(lang, "🧹 Сброс фильтров", "🧹 Reset filters"), callback_data="filters:reset")], [InlineKeyboardButton(text=_L(lang, "🌐 Remote: Вкл", "🌐 Remote: On"), callback_data="filters:force_remote")], _footer_row(lang)])
            return msg, kb
        return _render_card(lang, cards[idx], payload)
    if state == "about":
        txt = _L(lang,
                 "ℹ️ О боте\nЯ показываю вакансии из Adzuna, убираю шум и сортирую по релевантности. Фильтры можно менять в любой момент. Ничего лишнего — сразу ссылка на отклик.",
                 "ℹ️ About\nI fetch jobs from Adzuna, remove noise, and rank results by relevance. Update filters anytime. No fluff — direct apply link.")
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
        "search_filters": "menu",
        "search_card": "search_filters",
        "about": "menu",
        "support": "menu",
        "welcome": "welcome",
        "settings": "menu",
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
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    payload = row.payload or {"filters": {}}
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="settings", payload=payload)
    text, kb = _render_settings(lang, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "menu:search")
@router.callback_query(F.data == "search:quick")
async def open_filters(cq: CallbackQuery, session, t, lang: str):
    ui = UiSessionsRepo(session)
    payload = {"filters": {}, "input_mode": "filters:what"}
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state="search_filters", payload=payload)
    prompt = _L(lang, "Введите ключевые слова для поиска", "Enter job keywords")
    kb = InlineKeyboardMarkup(inline_keyboard=[_footer_row(lang)])
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, prompt, kb)
    await session.commit()
    await cq.answer("")


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
    state = row.screen_state or "search_filters"
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=state, payload=payload)
    text, kb = _render_screen(lang, state, payload)
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "filters:reset")
async def filters_reset(cq: CallbackQuery, session, t, lang: str):
    payload = {"filters": {"days": 7, "remote": False, "employment": []}}
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    state = row.screen_state or "search_filters"
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=state, payload=payload)
    text, kb = _render_screen(lang, state, payload)
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
    state = row.screen_state or "search_filters"
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=state, payload=payload)
    hint = _L(lang, f"Введите значение для {field}", f"Enter value for {field}")
    text, kb = _render_screen(lang, state, payload)
    text = f"{text}\n\n{hint}"
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await session.commit()
    await cq.answer("")


@router.message()
async def on_free_text(m: Message, session, t, lang: str):
    # Capture text if input_mode is set
    ui = UiSessionsRepo(session)
    row = await ui.upsert(m.chat.id, m.from_user.id)
    payload = (row.payload or {})
    input_mode = payload.get("input_mode")
    if not input_mode:
        return
    if input_mode.startswith("filters:"):
        _, field = input_mode.split(":", 1)
        f = payload.setdefault("filters", {})
        txt = m.text.strip()
        if field in {"salary_min", "days"}:
            try:
                f[field] = int(txt)
            except Exception:
                await m.reply(_L(lang, "Введите число", "Enter a number"))
                return
        else:
            if len(txt) < 2 or len(txt) > 50 or not all(ch.isalnum() or ch.isspace() for ch in txt):
                await m.reply(_L(lang, "Некорректный ввод", "Invalid input"))
                return
            f[field] = txt
        payload.pop("input_mode", None)
        state = row.screen_state or "search_filters"
        if field == "what" and not f.get("where"):
            payload["input_mode"] = "filters:where"
            await ui.upsert(m.chat.id, m.from_user.id, screen_state=state, payload=payload)
            prompt = _L(lang, "Укажите локацию", "Enter location")
            kb = InlineKeyboardMarkup(inline_keyboard=[_footer_row(lang)])
            await _edit_anchor(m, row.anchor_message_id or m.message_id, prompt, kb)
            await session.commit()
            return
        await ui.upsert(m.chat.id, m.from_user.id, screen_state=state, payload=payload)
        text, kb = _render_screen(lang, state, payload)
        await _edit_anchor(m, row.anchor_message_id or m.message_id, text, kb)
        await session.commit()
        return



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
    f = payload.get("filters", {})
    profile = DProfile(
        role=f.get("what") or "",
        skills=[],
        locations=[f.get("where")] if f.get("where") else [],
        salary_min=int(f.get("salary_min") or 0),
        salary_max=None,
        formats=[],
        experience_yrs=0,
    )
    params = SearchParams(max_days_old=int(f.get("days") or cfg.search.max_days_old_default), sort="relevance")
    if not f.get("what") or not f.get("where"):
        payload["error"] = _L(lang, "Укажите ключевые слова и локацию", "Provide keywords and location")
        results = []
    else:
        try:
            results = await adzuna.search("gb", 1, cfg.search.results_per_page, what=f.get("what"), where=f.get("where"), sort=params.sort, max_days_old=params.max_days_old)
        except HTTPStatusError as e:
            status = e.response.status_code
            if status in (401, 403):
                payload["error"] = _L(lang, "Ошибка API ключей", "API key error")
            elif status == 400:
                payload["error"] = _L(lang, "Неверные параметры поиска", "Invalid search parameters")
            else:
                payload["error"] = _L(lang, "Ошибка поиска вакансий", "Job search error")
            results = []
        except Exception:
            payload["error"] = _L(lang, "Ошибка поиска", "Search error")
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
