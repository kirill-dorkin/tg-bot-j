from __future__ import annotations

import re

import httpx
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.bot.fsm_states import SearchFSM
from app.bot.keyboards import card_kb
from app.config import AppConfig
from app.domain.models import Profile as DProfile, SearchParams
from app.domain.pipeline import process
from app.integrations.adzuna_client import AdzunaClient
from app.repositories.profiles import ProfilesRepo
from app.repositories.shortkeys import ShortKeysRepo
from app.telemetry.logger import get_logger
from .search import _format_card_message

router = Router()

log = get_logger("handlers.search_params")

_KEYWORD_RE = re.compile(r"[\w\s-]{3,50}")
_LOCATION_RE = re.compile(r"[\w\s,.-]{2,100}")


def _valid_keyword(text: str) -> bool:
    return bool(_KEYWORD_RE.fullmatch(text))


def _valid_location(text: str) -> bool:
    # location may contain city, region and commas
    return bool(_LOCATION_RE.fullmatch(text))


@router.message(SearchFSM.role)
async def handle_role(m: Message, state: FSMContext, session, t):
    txt = (m.text or "").strip()
    if not _valid_keyword(txt):
        await m.answer(t("errors.invalid_format"))
        return
    data = await state.get_data()
    flow = data.get("flow")
    if flow == "search":
        await state.update_data(role=txt)
        await state.set_state(SearchFSM.location)
        await m.answer(t("profile.form.locations"))
    elif flow == "edit_role":
        repo = ProfilesRepo(session)
        prof = await repo.get(m.from_user.id)
        await repo.upsert(
            user_id=m.from_user.id,
            role=txt,
            employment_types=prof.employment_types if prof else None,
            skills=prof.skills if prof else [],
            locations=prof.locations if prof else [],
            salary_min=prof.salary_min if prof else 0,
            salary_max=prof.salary_max if prof else None,
            formats=prof.formats if prof else [],
            experience_yrs=prof.experience_yrs if prof else 0,
        )
        await session.commit()
        await state.clear()
        await m.answer(t("profile.saved"))
    else:
        await state.clear()


@router.message(SearchFSM.location)
async def handle_location(
    m: Message,
    state: FSMContext,
    session,
    cfg: AppConfig,
    adzuna: AdzunaClient,
    store,
    t,
    lang: str,
):
    txt = (m.text or "").strip()
    if not _valid_location(txt):
        await m.answer(t("errors.invalid_location"))
        return
    data = await state.get_data()
    flow = data.get("flow")
    if flow == "search":
        role = data.get("role", "")
        repo = ProfilesRepo(session)
        await repo.upsert(
            user_id=m.from_user.id,
            role=role,
            employment_types=None,
            skills=[],
            locations=[txt],
            salary_min=0,
            salary_max=None,
            formats=[],
            experience_yrs=0,
        )
        await session.commit()
        profile = DProfile(
            role=role,
            skills=[],
            locations=[txt],
            salary_min=0,
            salary_max=None,
            formats=[],
            experience_yrs=0,
        )
        params = SearchParams(max_days_old=cfg.search.max_days_old_default, sort="relevance")
        try:
            results = await adzuna.search(
                "gb",
                1,
                cfg.search.results_per_page,
                what=role,
                where=txt,
                sort=params.sort,
                max_days_old=params.max_days_old,
            )
        except ValueError as e:
            log.warning("search.invalid_params", err=str(e))
            await m.answer(t("search.invalid_params").replace("{err}", str(e)))
            await state.clear()
            return
        except httpx.HTTPError as e:
            log.warning("search.api_error", err=str(e))
            await m.answer(t("search.api_error"))
            await state.clear()
            return

        pr = process(results, profile, params, cfg)
        if not pr["cards"]:
            msg = (
                t("search.no_results")
                .replace("{role}", role)
                .replace("{location}", txt)
            )
            await m.answer(msg)
        else:
            sk = ShortKeysRepo(store)
            for c in pr["cards"][:5]:
                key = await sk.generate({"act": "card", "args": {"url": c["apply_url"]}})
                await m.answer(_format_card_message(c, t), reply_markup=card_kb(c["apply_url"], key, t, lang))
            shown = min(5, len(pr["cards"]))
            total = len(pr["cards"])
            res_header = t("results.title")
            res_kpv_tpl = (t("results.kpv") or ["Shown: {shown} of {total}"])[0]
            res_line = res_kpv_tpl.replace("{shown}", str(shown)).replace("{total}", str(total))
            await m.answer(f"{res_header}\n———\n{res_line}")
        await state.clear()
    elif flow == "edit_location":
        repo = ProfilesRepo(session)
        prof = await repo.get(m.from_user.id)
        await repo.upsert(
            user_id=m.from_user.id,
            role=prof.role if prof else "",
            employment_types=prof.employment_types if prof else None,
            skills=prof.skills if prof else [],
            locations=[txt],
            salary_min=prof.salary_min if prof else 0,
            salary_max=prof.salary_max if prof else None,
            formats=prof.formats if prof else [],
            experience_yrs=prof.experience_yrs if prof else 0,
        )
        await session.commit()
        await state.clear()
        await m.answer(t("profile.saved"))
    else:
        await state.clear()
