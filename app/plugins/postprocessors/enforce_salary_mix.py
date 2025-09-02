from __future__ import annotations

from typing import Iterable

from app.domain.models import Card


def enforce(cards: list[Card]) -> list[Card]:
    # Do not show >2 consecutive without salary when alternatives exist
    result: list[Card] = []
    no_salary_streak = 0
    tail: list[Card] = []
    for c in cards:
        has_salary = "З/п не указана" not in c["subtitle"]
        if not has_salary:
            no_salary_streak += 1
        else:
            no_salary_streak = 0
        if no_salary_streak > 2:
            tail.append(c)
            continue
        result.append(c)
    # Append tail after enforcing
    result.extend(tail)
    return result

