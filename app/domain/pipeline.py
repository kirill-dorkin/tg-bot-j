from __future__ import annotations

from typing import Iterable

from app.config import AppConfig
from .dedup import deduplicate
from .filters import passes_filters
from .models import AdzunaRaw, Card, NormalizedJob, PipelineResult, Profile, SearchParams
from .normalization import normalize_item, summary_from_description
from .scoring import compute_score
from app.plugins.postprocessors.enforce_salary_mix import enforce


def process(
    items: Iterable[AdzunaRaw],
    profile: Profile,
    params: SearchParams,
    cfg: AppConfig,
) -> PipelineResult:
    normalized: list[NormalizedJob] = [normalize_item(i) for i in items]

    filtered: list[NormalizedJob] = []
    filtered_out = 0
    for j in normalized:
        if passes_filters(j, profile, params):
            filtered.append(j)
        else:
            filtered_out += 1

    deduped = deduplicate(filtered)
    dup_removed = len(filtered) - len(deduped)

    scored = [
        (j, compute_score(j, profile, cfg, params.category))
        for j in deduped
    ]

    # Sort by score desc; tie-breakers: has salary > fresher
    scored.sort(key=lambda x: (x[1], 1 if (x[0]["salary_min"] or x[0]["salary_max"]) else 0, x[0]["created"]), reverse=True)

    cards: list[Card] = []
    for j, sc in scored[:50]:  # cap to reasonable number before pagination
        title_line = f"{j['title']} — {j['company']}"
        subtitle = f"{j['city_region']} • {j['salary_text']} • {j['posted_at_human']}"
        summary = summary_from_description(j["description"], 300)
        short_reason = f"score={sc}"
        cards.append(
            {
                "title": title_line,
                "subtitle": subtitle,
                "summary": summary,
                "apply_url": j["redirect_url"],
                "short_reason": short_reason,
            }
        )

    cards = enforce(cards)

    return {
        "cards": cards,
        "shown": len(cards),
        "filtered_out_by_rules": filtered_out,
        "duplicates_removed": dup_removed,
    }

