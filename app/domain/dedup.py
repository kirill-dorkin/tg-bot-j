from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from .models import NormalizedJob


def _triple_key(j: NormalizedJob) -> str:
    return f"{j['title'].lower()}|{j['company'].lower()}|{(j['city_region'] or '').lower()}"


def choose_better(a: NormalizedJob, b: NormalizedJob) -> NormalizedJob:
    # Prefer wider salary range
    a_span = ((a.get("salary_max") or 0) - (a.get("salary_min") or 0))
    b_span = ((b.get("salary_max") or 0) - (b.get("salary_min") or 0))
    if a_span != b_span:
        return a if a_span > b_span else b
    # else newer
    return a if a["created"] >= b["created"] else b


def deduplicate(jobs: Iterable[NormalizedJob]) -> list[NormalizedJob]:
    by_url: dict[str, NormalizedJob] = OrderedDict()
    by_triple: dict[str, NormalizedJob] = OrderedDict()

    for j in jobs:
        url = j.get("redirect_url") or ""
        if url:
            prev = by_url.get(url)
            if prev:
                by_url[url] = choose_better(prev, j)
            else:
                by_url[url] = j
        t = _triple_key(j)
        prev_t = by_triple.get(t)
        if prev_t:
            by_triple[t] = choose_better(prev_t, j)
        else:
            by_triple[t] = j

    # Merge preferring url dict (keeps order)
    merged: dict[str, NormalizedJob] = OrderedDict()
    for j in by_url.values():
        merged[j["redirect_url"]] = j
    for j in by_triple.values():
        merged.setdefault(j["redirect_url"] or _triple_key(j), j)
    return list(merged.values())

