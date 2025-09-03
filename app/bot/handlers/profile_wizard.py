from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.keyboards import (
    pf_role_kb,
    pf_skills_kb,
    pf_locations_kb,
    pf_salary_kb,
    pf_formats_kb,
    pf_experience_kb,
    main_menu_kb,
    with_lang_row,
)
from app.repositories.profiles import ProfilesRepo


router = Router()


def _role_label(code: str, lang: str) -> str:
    mapping = {
        "frontend": "Frontend Developer",
        "backend": "Backend Developer",
        "fullstack": "Fullstack Developer",
        "mobile": "Mobile Developer",
        "devops": "DevOps",
        "data": "Data Engineer",
        "qa": "QA Engineer",
        "pm": "Product Manager",
        "design": "Designer",
    }
    return mapping.get(code, code)


def _skill_label(code: str) -> str:
    return {
        "react": "React",
        "ts": "TypeScript",
        "node": "Node.js",
        "python": "Python",
        "java": "Java",
        "go": "Go",
        "csharp": "C#",
        "php": "PHP",
        "kotlin": "Kotlin",
        "swift": "Swift",
        "cpp": "C++",
        "sql": "SQL",
    }.get(code, code)


def _loc_label(code: str, lang: str) -> str:
    return {
        "remote": "Remote" if lang != "ru" else "Remote",
        "eu": "EU",
        "us": "US",
        "uk": "UK",
        "ru": "Russia" if lang != "ru" else "Россия",
        "other": "Other" if lang != "ru" else "Другое",
    }.get(code, code)


@router.callback_query(F.data.startswith("pf:role:"))
async def pf_pick_role(cq: CallbackQuery, state: FSMContext, t, lang: str):
    code = cq.data.split(":")[2]
    label = _role_label(code, lang)
    data = await state.get_data()
    pf = data.get("pf", {})
    pf.update({"role": label})
    await state.update_data(pf=pf)
    # Next: skills
    text = f"{t('profile.form.title')}\n\n{t('profile.form.skills')}"
    selected = set(pf.get("skills", []))
    await cq.message.edit_text(text, reply_markup=pf_skills_kb(selected, lang))
    await cq.answer("")


@router.callback_query(F.data.startswith("pf:skills:"))
async def pf_toggle_skill(cq: CallbackQuery, state: FSMContext, t, lang: str):
    _, _, tail = cq.data.split(":", 2)
    data = await state.get_data()
    pf = data.get("pf", {})
    selected = set(pf.get("skills", []))
    if tail in ("next", "skip"):
        if tail == "skip":
            pf["skills"] = []
            await state.update_data(pf=pf)
        # proceed to locations
        text = f"{t('profile.form.title')}\n\n{t('profile.form.locations')}"
        locs = set(pf.get("loc_codes", []))
        await cq.message.edit_text(text, reply_markup=pf_locations_kb(locs, lang))
        await cq.answer("")
        return
    else:
        code = tail
        if code in selected:
            selected.remove(code)
        else:
            selected.add(code)
        pf["skills"] = list(selected)
    await state.update_data(pf=pf)
    text = f"{t('profile.form.title')}\n\n{t('profile.form.skills')}"
    await cq.message.edit_text(text, reply_markup=pf_skills_kb(set(pf.get("skills", [])), lang))
    await cq.answer("")


@router.callback_query(F.data.startswith("pf:loc:"))
async def pf_toggle_location(cq: CallbackQuery, state: FSMContext, t, lang: str):
    _, _, tail = cq.data.split(":", 2)
    data = await state.get_data()
    pf = data.get("pf", {})
    selected = set(pf.get("loc_codes", []))
    if tail in ("next", "skip"):
        if tail == "skip":
            pf["loc_codes"] = []
            await state.update_data(pf=pf)
        # proceed to salary
        text = f"{t('profile.form.title')}\n\n{t('profile.form.salary_min')}"
        await cq.message.edit_text(text, reply_markup=pf_salary_kb(lang))
        await cq.answer("")
        return
    code = tail
    if code in selected:
        selected.remove(code)
    else:
        selected.add(code)
    pf["loc_codes"] = list(selected)
    await state.update_data(pf=pf)
    text = f"{t('profile.form.title')}\n\n{t('profile.form.locations')}"
    await cq.message.edit_text(text, reply_markup=pf_locations_kb(set(pf.get("loc_codes", [])), lang))
    await cq.answer("")


@router.callback_query(F.data.startswith("pf:sal:"))
async def pf_pick_salary(cq: CallbackQuery, state: FSMContext, t, lang: str):
    code = cq.data.split(":")[2]
    data = await state.get_data()
    pf = data.get("pf", {})
    if code == "skip":
        pf["salary_min"] = 0
    else:
        try:
            pf["salary_min"] = int(code)
        except Exception:
            pf["salary_min"] = 0
    await state.update_data(pf=pf)
    # Next: formats
    text = f"{t('profile.form.title')}\n\n{t('profile.form.formats')}"
    selected = set(pf.get("formats", []))
    await cq.message.edit_text(text, reply_markup=pf_formats_kb(selected, lang))
    await cq.answer("")


@router.callback_query(F.data.startswith("pf:fmt:"))
async def pf_toggle_format(cq: CallbackQuery, state: FSMContext, t, lang: str):
    _, _, tail = cq.data.split(":", 2)
    data = await state.get_data()
    pf = data.get("pf", {})
    selected = set(pf.get("formats", []))
    if tail in ("next", "skip"):
        if tail == "skip":
            pf["formats"] = []
            await state.update_data(pf=pf)
        # Next: experience
        text = f"{t('profile.form.title')}\n\n{t('profile.form.experience')}"
        await cq.message.edit_text(text, reply_markup=pf_experience_kb(lang))
        await cq.answer("")
        return
    code = tail
    if code in selected:
        selected.remove(code)
    else:
        selected.add(code)
    pf["formats"] = list(selected)
    await state.update_data(pf=pf)
    text = f"{t('profile.form.title')}\n\n{t('profile.form.formats')}"
    await cq.message.edit_text(text, reply_markup=pf_formats_kb(set(pf.get("formats", [])), lang))
    await cq.answer("")


@router.callback_query(F.data.startswith("pf:exp:"))
async def pf_pick_experience(cq: CallbackQuery, state: FSMContext, session, t, lang: str):
    code = cq.data.split(":")[2]
    try:
        years = int(code)
    except Exception:
        years = 0
    data = await state.get_data()
    pf = data.get("pf", {})
    pf["experience_yrs"] = years
    # Persist
    repo = ProfilesRepo(session)
    role = pf.get("role") or ""
    skills_codes = pf.get("skills", [])
    skills = [_skill_label(c) for c in skills_codes]
    loc_codes = pf.get("loc_codes", [])
    locations = [_loc_label(code, lang) for code in loc_codes]
    salary_min = int(pf.get("salary_min", 0) or 0)
    formats = pf.get("formats", [])
    await repo.upsert(
        user_id=cq.from_user.id,
        role=role,
        skills=skills,
        locations=locations,
        salary_min=salary_min,
        salary_max=None,
        formats=formats,
        experience_yrs=years,
    )
    await session.commit()
    # Clear temp
    await state.update_data(pf={})
    # Replace the whole block with the main menu and explanation
    kb = with_lang_row(main_menu_kb(t), lang, t)
    text = f"{t('menu.title')}\n{t('menu.sub')}"
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer("")
