from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict
try:  # Python <3.11 compat
    from typing import NotRequired  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    from typing_extensions import NotRequired  # type: ignore


class AdzunaRaw(TypedDict):
    title: str
    company: dict
    location: dict
    created: str
    redirect_url: str
    salary_min: NotRequired[float | None]
    salary_max: NotRequired[float | None]
    category: NotRequired[dict]
    description: str


@dataclass
class Profile:
    role: str
    skills: list[str]
    locations: list[str]
    salary_min: int
    salary_max: int | None
    formats: list[str]
    experience_yrs: int


@dataclass
class SearchParams:
    what: str | None = None
    where: str | None = None
    distance_km: int | None = None
    max_days_old: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    contract_type: Literal["permanent", "contract"] | None = None
    employment_type: Literal["full_time", "part_time"] | None = None
    category: str | None = None
    sort: Literal["relevance", "date"] | None = None


class NormalizedJob(TypedDict):
    title: str
    company: str
    city_region: str
    created: datetime
    posted_at_human: str
    redirect_url: str
    salary_min: int | None
    salary_max: int | None
    salary_text: str
    category_label: str | None
    category_tag: str | None
    description: str


class Card(TypedDict):
    title: str
    subtitle: str
    summary: str
    apply_url: str
    short_reason: str


class PipelineResult(TypedDict):
    cards: list[Card]
    shown: int
    filtered_out_by_rules: int
    duplicates_removed: int
