from __future__ import annotations

from typing import Any

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.fsm_states import SearchFSM
from app.bot.keyboards import settings_kb
from app.repositories.profiles import ProfilesRepo
from app.repositories.ui_sessions import UiSessionsRepo
from app.repositories.users import UsersRepo


router = Router()


def _L(lang: str, ru: str, en: str) -> str:
    return ru if lang == "ru" else en


def _lang_row(lang: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text=_L(lang, "🇷🇺 Русский", "🇷🇺 Russian"), callback_data="lang:set:ru"),
        InlineKeyboardButton(text=_L(lang, "🇬🇧 English", "🇬🇧 English"), callback_data="lang:set:en"),
    ]


def _footer_row(lang: str, allow_menu: bool = True) -> list[InlineKeyboardButton]:
    row = [InlineKeyboardButton(text=_L(lang, "⬅️ Назад", "⬅️ Back"), callback_data="nav:back")]
    if allow_menu:
        row.append(InlineKeyboardButton(text=_L(lang, "🏠 Меню", "🏠 Menu"), callback_data="nav:menu"))
    row.append(InlineKeyboardButton(text="🌐 RU | EN", callback_data="lang:toggle"))
    return row


async def _ensure_anchor_and_state(msg: Message, session) -> tuple[int, dict[str, Any]]:
    repo = UiSessionsRepo(session)
    row = await repo.get(msg.chat.id, msg.from_user.id)
    if row and row.anchor_message_id:
        return row.anchor_message_id, {"screen_state": row.screen_state, "payload": row.payload}
    lang = "ru"
    welcome, kb = _render_welcome(lang)
    sent = await msg.answer(welcome, reply_markup=kb)
    await repo.upsert(
        msg.chat.id,
        msg.from_user.id,
        anchor_message_id=sent.message_id,
        screen_state="welcome",
        payload={},
    )
    await session.commit()
    return sent.message_id, {"screen_state": "welcome", "payload": {}}


async def _edit_anchor(
    cq_or_msg: CallbackQuery | Message, anchor_id: int, text: str, kb: InlineKeyboardMarkup | None = None
):
    chat_id = cq_or_msg.message.chat.id if isinstance(cq_or_msg, CallbackQuery) else cq_or_msg.chat.id
    bot = cq_or_msg.bot if isinstance(cq_or_msg, CallbackQuery) else cq_or_msg.bot
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=anchor_id, text=text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        raise


def _menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_L(lang, "🔍 Поиск вакансий", "🔍 Job search"), callback_data="menu:search")],
        [InlineKeyboardButton(text=_L(lang, "⚙️ Настроить фильтры", "⚙️ Set filters"), callback_data="menu:settings")],
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
        text, kb = _render_screen(lang, state["screen_state"], state["payload"])
        await _edit_anchor(m, anchor_id, text, kb)


def _render_welcome(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    txt = _L(
        lang,
        "👋 Привет! Я помогу быстро найти релевантные вакансии под твой профиль.\n\nЧто внутри:\n• Источник: Adzuna\n• Умные фильтры по навыкам, локации и зарплате\n• Короткие карточки с прямой ссылкой на отклик\n\n🌍 Выбери язык интерфейса:",
        "👋 Hi! I help you quickly find relevant jobs for your profile.\n\nWhat you get:\n• Source: Adzuna\n• Smart filters by skills, location, salary\n• Concise cards with a direct apply link\n\n🌍 Choose interface language:",
    )
    return txt, InlineKeyboardMarkup(inline_keyboard=[_lang_row(lang)])


@router.callback_query(F.data.startswith("lang:set:"))
async def on_lang_set(cq: CallbackQuery, session):
    _, _, target = cq.data.split(":", 2)
    lang = "ru" if target == "ru" else "en"
    ui = UiSessionsRepo(session)
    row = await ui.upsert(cq.message.chat.id, cq.from_user.id)
    await UsersRepo(session).set_lang(cq.from_user.id, lang)
    menu_text, kb = _render_menu(lang)
    text = _L(lang, "✅ Язык сохранён.\n\n", "✅ Language saved.\n\n") + menu_text
    await _edit_anchor(cq, row.anchor_message_id or cq.message.message_id, text, kb)
    await ui.set_state(cq.message.chat.id, cq.from_user.id, screen_state="menu", payload={})
    await session.commit()
    await cq.answer("")


@router.callback_query(F.data == "lang:toggle")
async def on_lang_toggle(cq: CallbackQuery, session):
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


def _render_screen(lang: str, state: str, payload: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    if state == "welcome":
        return _render_welcome(lang)
    if state == "menu":
        return _render_menu(lang)
    if state == "about":
        txt = _L(
            lang,
            "ℹ️ О боте\nЯ показываю вакансии из Adzuna, убираю шум и сортирую по релевантности. Профиль и фильтры можно менять в любой момент. Ничего лишнего — сразу ссылка на отклик.",
            "ℹ️ About\nI fetch jobs from Adzuna, remove noise, and rank results by relevance. Update your profile and filters anytime. No fluff — direct apply link.",
        )
        return txt, InlineKeyboardMarkup(inline_keyboard=[_footer_row(lang)])
    if state == "support":
        txt = _L(
            lang,
            "🆘 Поддержка\nОпишите вопрос одной строкой или откройте чат поддержки.",
            "🆘 Support\nDescribe your issue briefly or open support chat.",
        )
        rows = [
            [
                InlineKeyboardButton(text=_L(lang, "💬 Открыть чат", "💬 Open chat"), url="https://t.me/"),
                InlineKeyboardButton(text=_L(lang, "✉️ Email", "✉️ Email"), url="mailto:support@example.com"),
            ],
            _footer_row(lang),
        ]
        return txt, InlineKeyboardMarkup(inline_keyboard=rows)
    return _render_menu(lang)


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
    back_map = {
        "about": "menu",
        "support": "menu",
        "welcome": "welcome",
    }
    new_state = back_map.get(state, "menu")
    await ui.upsert(cq.message.chat.id, cq.from_user.id, screen_state=new_state, payload=row.payload or {})
    text, kb = _render_screen(lang, new_state, row.payload or {})
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
async def menu_settings(cq: CallbackQuery, session, t):
    prof = await ProfilesRepo(session).get(cq.from_user.id)
    role = prof.role if prof and prof.role else "—"
    loc = prof.locations[0] if prof and prof.locations else "—"
    text = (
        f"{t('settings.title')}\n{t('settings.sub')}\n———\n"
        f"{t('profile.form.role')}: {role}\n"
        f"{t('profile.form.locations')}: {loc}"
    )
    await cq.message.answer(text, reply_markup=settings_kb(t))
    await cq.answer("")


@router.callback_query(F.data == "menu:search")
async def menu_search(cq: CallbackQuery, state, t):
    await state.set_state(SearchFSM.role)
    await state.update_data(flow="search")
    await cq.message.answer(t("profile.form.role"))
    await cq.answer("")


