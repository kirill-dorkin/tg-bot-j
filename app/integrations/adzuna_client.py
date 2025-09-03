from __future__ import annotations

import asyncio
from typing import Any, Sequence

import httpx

from app.config import AppConfig, Settings
from app.infra.http import create_async_client
from app.telemetry.metrics import timer
from app.telemetry.logger import get_logger


log = get_logger("adzuna")


class AdzunaClient:
    def __init__(self, settings: Settings, cfg: AppConfig) -> None:
        self._settings = settings
        self._cfg = cfg
        self._client: httpx.AsyncClient | None = None

    def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            t = self._cfg.timeouts
            self._client = create_async_client(t.adzuna_connect, t.adzuna_read, t.total)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        country: str,
        page: int,
        results_per_page: int,
        *,
        what: str | None = None,
        where: str | None = None,
        sort: str | None = None,
        max_days_old: int | None = None,
        salary_min: int | None = None,
    ) -> list[dict[str, Any]]:
        base = self._settings.ADZUNA_BASE_URL.rstrip("/")
        url = f"{base}/{country}/search/{page}"
        params: dict[str, Any] = {
            "app_id": self._settings.ADZUNA_APP_ID,
            "app_key": self._settings.ADZUNA_APP_KEY,
            "results_per_page": results_per_page,
        }
        if what:
            params["what"] = what
        if where:
            params["where"] = where
        if sort:
            params["sort_by"] = sort
        if max_days_old is not None:
            params["max_days_old"] = max_days_old
        if salary_min is not None:
            params["salary_min"] = salary_min

        client = self._client_or_create()
        backoffs = [0.2, 0.4, 0.8]
        for attempt, backoff in enumerate(backoffs, start=1):
            try:
                with timer("adzuna_search", attempt=str(attempt)):
                    resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                # Use only allowed fields
                out: list[dict[str, Any]] = []
                for it in data.get("results", []):
                    out.append(
                        {
                            "title": it.get("title"),
                            "company": {"display_name": (it.get("company") or {}).get("display_name")},
                            "location": {"display_name": (it.get("location") or {}).get("display_name")},
                            "created": it.get("created"),
                            "redirect_url": it.get("redirect_url"),
                            "salary_min": it.get("salary_min"),
                            "salary_max": it.get("salary_max"),
                            "category": {
                                "label": (it.get("category") or {}).get("label"),
                                "tag": (it.get("category") or {}).get("tag"),
                            },
                            "description": it.get("description") or "",
                        }
                    )
                return out
            except Exception as e:  # noqa: BLE001
                log.warning("adzuna.search.error", attempt=attempt, err=str(e))
                if attempt == len(backoffs):
                    raise
                await asyncio.sleep(backoff)
        return []

