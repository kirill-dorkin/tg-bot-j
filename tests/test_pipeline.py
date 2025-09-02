from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.config import AppConfig
from app.domain.models import AdzunaRaw, Profile, SearchParams
from app.domain.pipeline import process
from app.domain.dedup import deduplicate
from app.domain.normalization import normalize_item
from app.domain.scoring import title_desc_skill_score
from app.plugins.postprocessors.enforce_salary_mix import enforce


def make_raw(title: str, company: str, city: str, days_ago: int, desc: str = "", url: str = "u") -> AdzunaRaw:
    created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "title": title,
        "company": {"display_name": company},
        "location": {"display_name": city},
        "created": created,
        "redirect_url": url,
        "salary_min": None,
        "salary_max": None,
        "category": {"label": "IT Jobs", "tag": "it"},
        "description": desc,
    }


def base_profile() -> Profile:
    return Profile(
        role="Frontend Developer",
        skills=["React", "TypeScript", "Next.js", "Node.js"],
        locations=["Berlin", "Remote", "EU"],
        salary_min=2500,
        salary_max=None,
        formats=["remote", "hybrid", "onsite"],
        experience_yrs=1,
    )


def test_filter_by_skills():
    cfg = AppConfig()
    prof = base_profile()
    params = SearchParams(max_days_old=14)
    raw = [
        make_raw("Python Dev", "Acme", "Berlin", 0, desc="Python only", url="1"),
        make_raw("React Dev", "Acme", "Berlin", 0, desc="React and TS", url="2"),
    ]
    pr = process(raw, prof, params, cfg)
    # Only one should pass (>=2 skills)
    assert pr["filtered_out_by_rules"] >= 1


def test_remote_location_marker():
    cfg = AppConfig()
    prof = base_profile()
    params = SearchParams(max_days_old=14)
    raw = [
        make_raw("React Dev", "Acme", "Munich", 0, desc="Remote work available TypeScript", url="3"),
    ]
    pr = process(raw, prof, params, cfg)
    assert pr["shown"] >= 1


def test_dedup_by_url_and_triple():
    a = normalize_item(make_raw("React Dev", "Acme", "Berlin", 0, url="same"))
    b = normalize_item(make_raw("React Dev", "Acme", "Berlin", 1, url="same"))
    c = normalize_item(make_raw("React Dev", "Acme", "Berlin", 2, url="diff"))
    d = normalize_item(make_raw("React Dev", "Acme", "Berlin", 3, url="diff2"))
    out = deduplicate([a, b, c, d])
    # same url => one; triple duplicate also dedup
    assert len(out) <= 3


def test_title_desc_skill_threshold():
    prof = base_profile()
    job = normalize_item(make_raw("React TypeScript Developer", "Acme", "Berlin", 0, desc="React and TS"))
    td = title_desc_skill_score(job, prof)
    assert td >= 0.4


def test_anti_noise_enforcer():
    # Build subtitles to check sequence: insert >2 without salary
    cards = [
        {"title": "a", "subtitle": "x • З/п не указана • y", "summary": "", "apply_url": "", "short_reason": ""},
        {"title": "b", "subtitle": "x • З/п не указана • y", "summary": "", "apply_url": "", "short_reason": ""},
        {"title": "c", "subtitle": "x • З/п не указана • y", "summary": "", "apply_url": "", "short_reason": ""},
        {"title": "d", "subtitle": "x • €1 • y", "summary": "", "apply_url": "", "short_reason": ""},
    ]
    out = enforce(cards)
    # First two stay, third moves later
    assert out[0]["title"] == "a" and out[1]["title"] == "b"
    assert any(c["title"] == "c" for c in out[2:])
