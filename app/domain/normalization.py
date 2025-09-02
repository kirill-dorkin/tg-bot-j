from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Iterable

from .models import AdzunaRaw, NormalizedJob


_TAG_RE = re.compile(r"<[^>]+>")
_MD_RE = re.compile(r"(^|\s)[*_#>`~]{1,3}")
_WS_RE = re.compile(r"\s+")


def _strip_text(text: str) -> str:
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = _MD_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _first_city_region(location_display: str) -> str:
    parts = [p.strip() for p in location_display.split(",") if p and p.strip()]
    if not parts:
        return ""
    return parts[0]


def _salary_text(min_v: int | None, max_v: int | None, currency: str = "€") -> str:
    def fmt(n: int) -> str:
        return f"{currency}{n:,}".replace(",", " ")

    if min_v and max_v:
        return f"{fmt(min_v)}–{fmt(max_v)}"
    if min_v and not max_v:
        return f"от {fmt(min_v)}"
    if max_v and not min_v:
        return f"до {fmt(max_v)}"
    return "З/п не указана"


def _posted_human(created: datetime) -> str:
    now = datetime.now(timezone.utc)
    if created > now:
        created = now
    days = (now - created).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "вчера"
    return f"{days} дн. назад"


def summary_from_description(desc: str, limit: int = 300) -> str:
    text = _strip_text(desc)
    if len(text) <= limit:
        return text
    # cut on word boundary
    cut = text[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut


def normalize_item(raw: AdzunaRaw) -> NormalizedJob:
    created = datetime.fromisoformat(raw["created"]).astimezone(timezone.utc)
    title = _strip_text(raw.get("title", "").strip())
    company = _strip_text(raw.get("company", {}).get("display_name", "") or "Компания не указана")
    loc_display = _strip_text(raw.get("location", {}).get("display_name", ""))
    city_region = _first_city_region(loc_display)
    salary_min = int(raw.get("salary_min") or 0) or None
    salary_max = int(raw.get("salary_max") or 0) or None
    desc = _strip_text(raw.get("description", ""))
    category = raw.get("category") or {}
    return {
        "title": title,
        "company": company,
        "city_region": city_region,
        "created": created,
        "posted_at_human": _posted_human(created),
        "redirect_url": raw.get("redirect_url", ""),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_text": _salary_text(salary_min, salary_max),
        "category_label": category.get("label"),
        "category_tag": category.get("tag"),
        "description": desc,
    }

