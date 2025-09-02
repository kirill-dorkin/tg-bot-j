from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

from .models import NormalizedJob, Profile, SearchParams


REMOTE_MARKERS = [
    "remote",
    "remotely",
    "удаленно",
    "home office",
]


def _normalize_skill(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("javascript", "js")
    s = s.replace("typescript", "ts")
    return s


def skill_matches(text: str, skills: Iterable[str]) -> int:
    t = text.lower().replace("javascript", "js").replace("typescript", "ts")
    count = 0
    for sk in skills:
        skn = _normalize_skill(sk)
        if re.search(rf"\b{re.escape(skn)}\b", t):
            count += 1
    return count


def has_remote_marker(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in REMOTE_MARKERS)


def location_ok(job: NormalizedJob, profile: Profile, params: SearchParams) -> bool:
    # if job city/region in preferred locations OR remote marker in desc
    locs = [l.lower() for l in profile.locations]
    if params.where:
        locs.append(params.where.lower())
    if job["city_region"].lower() in locs:
        return True
    if has_remote_marker(job["description"]):
        return True
    return False


def salary_ok(job: NormalizedJob, profile: Profile, params: SearchParams) -> bool:
    min_required = params.salary_min or profile.salary_min
    if min_required is None:
        return True
    min_job = job.get("salary_min")
    max_job = job.get("salary_max")
    if min_job is None and max_job is None:
        # allow when unspecified but negotiable marker present
        if re.search(r"competitive|negotiable|market rate|по договоренности", job["description"], re.I):
            return True
        return True  # be permissive in filter; ranking will penalize
    # explicit numbers
    if max_job is not None and max_job < min_required:
        if re.search(r"competitive|negotiable|market rate|по договоренности", job["description"], re.I):
            return True
        return False
    if min_job is not None and min_job < min_required and (max_job or 0) < min_required:
        return False
    return True


def contract_ok(job: NormalizedJob, params: SearchParams, raw_category: str | None) -> bool:
    # We do not have explicit employment/contract fields in normalized job; rely on params check only if provided.
    # Adzuna may have category label/tag which can be checked when provided in params.category
    if params.category:
        label = (job.get("category_label") or "") + " " + (job.get("category_tag") or "")
        if params.category.lower() not in label.lower():
            return False
    return True


def age_ok(job: NormalizedJob, params: SearchParams) -> bool:
    if not params.max_days_old:
        return True
    now = datetime.now(timezone.utc)
    return (now - job["created"]).days <= params.max_days_old


def passes_filters(job: NormalizedJob, profile: Profile, params: SearchParams) -> bool:
    # skills: need >=2 matches across title + description
    skills = profile.skills
    m = skill_matches(job["title"] + " " + job["description"], skills)
    if m < 2:
        return False
    if not location_ok(job, profile, params):
        return False
    if not salary_ok(job, profile, params):
        return False
    if not contract_ok(job, params, job.get("category_label")):
        return False
    if not age_ok(job, params):
        return False
    return True
