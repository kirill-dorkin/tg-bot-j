from __future__ import annotations

import re
from datetime import datetime, timezone

from app.config import AppConfig
from .models import NormalizedJob, Profile


CLICKBAIT_PATTERNS = [
    r"urgent|immediate start|limited time|superstar|rockstar|ninja",
]


def _norm(text: str) -> str:
    t = text.lower()
    t = t.replace("javascript", "js").replace("typescript", "ts")
    return t


def title_desc_skill_score(job: NormalizedJob, profile: Profile) -> float:
    # TF in title (weight 2) and desc (1)
    title = _norm(job["title"])
    desc = _norm(job["description"])
    skills = [_norm(s) for s in profile.skills]
    if not skills:
        return 0.0
    title_hits = sum(2 for s in skills if re.search(rf"\b{re.escape(s)}\b", title))
    desc_hits = sum(1 for s in skills if re.search(rf"\b{re.escape(s)}\b", desc))
    tf = (title_hits + desc_hits) / (3 * len(skills))
    return min(1.0, tf)


def location_score(job: NormalizedJob, profile: Profile) -> float:
    jr = (job["city_region"] or "").lower()
    prefs = [p.lower() for p in profile.locations]
    if jr in prefs:
        return 1.0
    if re.search(r"remote|remotely|удаленно|home office", job["description"], re.I):
        return 1.0
    # region/country fuzzy fallback
    for p in prefs:
        if p and p in jr:
            return 0.7
    return 0.0


def salary_score(job: NormalizedJob, profile: Profile) -> float:
    min_required = profile.salary_min
    if job["salary_min"] is None and job["salary_max"] is None:
        if re.search(r"competitive|negotiable|market rate|по договоренности", job["description"], re.I):
            return 0.5
        return 0.2
    min_job = job.get("salary_min") or 0
    max_job = job.get("salary_max") or 0
    if max_job and max_job < min_required:
        return 0.0
    if min_job and min_job <= min_required <= (max_job or min_job):
        return 1.0
    if min_job >= min_required:
        return 1.0
    return 0.5


def freshness_score(job: NormalizedJob) -> float:
    now = datetime.now(timezone.utc)
    days = (now - job["created"]).days
    if days <= 0:
        return 1.0
    if days == 1:
        return 0.8
    if days <= 7:
        return 0.6
    if days <= 14:
        return 0.3
    return 0.1


def category_score(job: NormalizedJob, preferred: str | None) -> float:
    if not preferred:
        return 0.6
    label = ((job.get("category_label") or "") + " " + (job.get("category_tag") or "")).lower()
    return 1.0 if preferred.lower() in label else 0.0


def is_clickbait(title: str) -> bool:
    return any(re.search(p, title, re.I) for p in CLICKBAIT_PATTERNS)


def compute_score(job: NormalizedJob, profile: Profile, cfg: AppConfig, preferred_category: str | None) -> float:
    w = cfg.scoring.weights
    td = title_desc_skill_score(job, profile)
    loc = location_score(job, profile)
    sal = salary_score(job, profile)
    fr = freshness_score(job)
    cat = category_score(job, preferred_category)
    score = (
        w.title_desc * td + w.location * loc + w.salary * sal + w.freshness * fr + w.category * cat
    )
    score = score / 100.0 * 100.0
    if td < 0.4:
        score = score * 0.7
    if is_clickbait(job["title"]):
        score = score * cfg.scoring.clickbait_multiplier
    return round(score, 2)

