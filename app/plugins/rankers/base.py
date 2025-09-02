from __future__ import annotations

from typing import Protocol

from app.domain.models import NormalizedJob, Profile


class Ranker(Protocol):
    def extra_score(self, job: NormalizedJob, profile: Profile) -> float: ...

