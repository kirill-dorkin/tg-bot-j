from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
import asyncio

from app.config import AppConfig
from app.domain.models import Profile as DProfile, SearchParams
from app.domain.pipeline import process
from app.integrations.adzuna_client import AdzunaClient
from app.repositories.profiles import ProfilesRepo
from app.repositories.shortkeys import ShortKeysRepo
from app.bot.keyboards import card_kb, search_filters_kb, empty_search_suggestions_kb, main_menu_kb, with_lang_row


router = Router()


def _format_card_message(card: dict, t) -> str:
    """Render a vacancy card using i18n templates."""
    raw_title = card.get("title", "")
    title, company = raw_title, ""
    if " — " in raw_title:
        title, company = raw_title.split(" — ", 1)

    subtitle = card.get("subtitle", "")
    parts = [p.strip() for p in subtitle.split("•")] if subtitle else []
    city = parts[0] if len(parts) > 0 else "—"
    salary = parts[1] if len(parts) > 1 else ""
    if not salary or salary == "З/п не указана":
        salary = t("card.salary_unknown")
    posted_raw = parts[2] if len(parts) > 2 else ""
    if posted_raw == "сегодня":
        posted = t("card.posted.today")
    elif posted_raw == "вчера":
        posted = t("card.posted.yesterday")
    elif posted_raw.endswith(" дн. назад"):
        days = posted_raw.split()[0]
        posted = (t("card.posted.days_ago") or "{days} дн. назад").replace("{days}", days)
    else:
        posted = posted_raw or "—"

    line1_tpl = t("card.line1") if callable(getattr(t, "__call__", None)) else "💼 {title} — {company}"
    line2_tpl = t("card.line2") if callable(getattr(t, "__call__", None)) else "📍 {city_region}   💰 {salary}   ⏱ {posted_human}"
    summary_tpl = t("card.summary") if callable(getattr(t, "__call__", None)) else "🧩 {summary}"

    line1 = line1_tpl.replace("{title}", title).replace("{company}", company)
    line2 = (
        line2_tpl
        .replace("{city_region}", city)
        .replace("{city}", city)
        .replace("{salary}", salary)
        .replace("{posted_human}", posted)
        .replace("{posted}", posted)
    )
    summary_line = summary_tpl.replace("{summary}", card.get("summary", ""))
    return "\n".join([line1, line2, summary_line])


@router.message(F.text == "/find")
async def find_cmd(m: Message, session, cfg: AppConfig, adzuna: AdzunaClient, store, t, lang: str):
    # Progress: three short steps
    await m.answer(t("search.progress.step1"))
    await asyncio.sleep(0.35)
    await m.answer(t("search.progress.step2"))
    await asyncio.sleep(0.35)
    await m.answer(t("search.progress.step3"))
    prof = await ProfilesRepo(session).get(m.from_user.id)
    if not prof:
        # No profile yet: show short hint per spec
        await m.answer(t("search.sub"))
        return
    profile = DProfile(
        role=prof.role or "",
        skills=prof.skills or [],
        locations=prof.locations or [],
        salary_min=prof.salary_min or 0,
        salary_max=prof.salary_max,
        formats=prof.formats or [],
        experience_yrs=prof.experience_yrs or 0,
    )
    params = SearchParams(max_days_old=cfg.search.max_days_old_default, sort="relevance")
    try:
        results = await adzuna.search("gb", 1, cfg.search.results_per_page, what=profile.role, where=profile.locations[0] if profile.locations else None, sort=params.sort, max_days_old=params.max_days_old)
    except Exception:
        results = []
    pr = process(results, profile, params, cfg)
    if not pr["cards"]:
        # Empty screen with hint
        text = f"{t('search.empty')}\n———\n{t('search.empty.hint')}"
        await m.answer(text, reply_markup=empty_search_suggestions_kb(t, lang))
        return
    sk = ShortKeysRepo(store)
    for c in pr["cards"][:5]:
        key = await sk.generate({"act": "card", "args": {"url": c["apply_url"]}})
        await m.answer(_format_card_message(c, t), reply_markup=card_kb(c["apply_url"], key, t, lang))

    # Results summary
    shown = min(5, len(pr["cards"]))
    total = len(pr["cards"])  # API total not available; use current batch
    res_header = t("results.title")
    res_kpv_tpl = (t("results.kpv") or ["Показано: {shown} из {total}"])[0]
    res_line = res_kpv_tpl.replace("{shown}", str(shown)).replace("{total}", str(total))
    await m.answer(f"{res_header}\n———\n{res_line}")


@router.callback_query(F.data == "menu:find")
async def open_search_filters(cq: CallbackQuery, session, cfg: AppConfig, t, lang: str):
    # Build state line from profile + defaults
    prof = await ProfilesRepo(session).get(cq.from_user.id)
    what = (prof.role if prof and prof.role else "-")
    where = (prof.locations[0] if prof and prof.locations else "-")
    distance = "-"
    days = str(cfg.search.max_days_old_default)
    contract = "-"
    employment = "-"
    category = "-"
    sort = "relevance"
    state_line = f"what: \"{what}\" | where: \"{where}\" | distance_km: {distance} | max_days_old: {days} | contract: {contract} | employment: {employment} | category: {category} | sort: {sort}"
    await cq.message.answer(f"{t('search.title')}\n{state_line}", reply_markup=search_filters_kb(t, lang))
    await cq.answer("")


@router.callback_query(F.data == "search:back")
async def search_back(cq: CallbackQuery, t, lang: str):
    kb = with_lang_row(main_menu_kb(t), lang, t)
    await cq.message.answer(t("menu.title"), reply_markup=kb)
    await cq.answer("")


@router.callback_query(F.data == "search:start")
async def search_start(cq: CallbackQuery, session, cfg: AppConfig, adzuna: AdzunaClient, store, t, lang: str):
    # Trigger same flow as /find
    await cq.message.answer(t("search.progress.step1"))
    await asyncio.sleep(0.35)
    await cq.message.answer(t("search.progress.step2"))
    await asyncio.sleep(0.35)
    await cq.message.answer(t("search.progress.step3"))
    prof = await ProfilesRepo(session).get(cq.from_user.id)
    if not prof:
        await cq.message.answer(t("search.sub"))
        await cq.answer("")
        return
    profile = DProfile(
        role=prof.role or "",
        skills=prof.skills or [],
        locations=prof.locations or [],
        salary_min=prof.salary_min or 0,
        salary_max=prof.salary_max,
        formats=prof.formats or [],
        experience_yrs=prof.experience_yrs or 0,
    )
    params = SearchParams(max_days_old=cfg.search.max_days_old_default, sort="relevance")
    try:
        results = await adzuna.search("gb", 1, cfg.search.results_per_page, what=profile.role, where=profile.locations[0] if profile.locations else None, sort=params.sort, max_days_old=params.max_days_old)
    except Exception:
        results = []
    pr = process(results, profile, params, cfg)
    if not pr["cards"]:
        text = f"{t('search.empty')}\n———\n{t('search.empty.hint')}"
        await cq.message.answer(text, reply_markup=empty_search_suggestions_kb(t, lang))
        await cq.answer("")
        return
    sk = ShortKeysRepo(store)
    for c in pr["cards"][:5]:
        key = await sk.generate({"act": "card", "args": {"url": c["apply_url"]}})
        await cq.message.answer(_format_card_message(c, t), reply_markup=card_kb(c["apply_url"], key, t, lang))
    shown = min(5, len(pr["cards"]))
    total = len(pr["cards"])  # API total not available
    res_header = t("results.title")
    res_kpv_tpl = (t("results.kpv") or ["Shown: {shown} of {total}"])[0]
    res_line = res_kpv_tpl.replace("{shown}", str(shown)).replace("{total}", str(total))
    await cq.message.answer(f"{res_header}\n———\n{res_line}")
    await cq.answer("")
