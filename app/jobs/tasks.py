from __future__ import annotations

from typing import Sequence

from app.config import AppConfig
from app.domain.models import Card
from app.integrations.adzuna_client import AdzunaClient


async def send_subscriptions(cfg: AppConfig, adzuna: AdzunaClient) -> None:
    # Placeholder: in real impl, load subs from DB, per user run pipeline and send up to 7 cards
    return


def select_digest(cards: Sequence[Card], limit: int = 7) -> list[Card]:
    return list(cards)[:limit]
