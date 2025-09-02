from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from app.domain.models import NormalizedJob, Profile
from .base import Ranker


def _tokens(text: str) -> list[str]:
    t = re.sub(r"[^a-zA-Z0-9+_.-]", " ", text.lower())
    t = t.replace("javascript", "js").replace("typescript", "ts")
    return [w for w in t.split() if len(w) > 1]


class TfidfTitleDescRanker(Ranker):
    def extra_score(self, job: NormalizedJob, profile: Profile) -> float:
        # Simple TF weighting relative to provided skills
        sk = {s.lower().replace("javascript", "js").replace("typescript", "ts") for s in profile.skills}
        if not sk:
            return 0.0
        tokens = _tokens(job["title"]) * 2 + _tokens(job["description"])  # weight title tokens
        tf = Counter(tokens)
        total = sum(tf.values()) or 1
        score = sum(tf.get(s, 0) for s in sk) / total
        return min(1.0, score)

