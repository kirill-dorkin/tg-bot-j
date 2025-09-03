from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Timeouts(BaseModel):
    adzuna_connect: int = 3
    adzuna_read: int = 7
    total: int = 10


class ScoringWeights(BaseModel):
    title_desc: int = 45
    location: int = 20
    salary: int = 15
    freshness: int = 10
    category: int = 10


class Scoring(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    clickbait_multiplier: float = 0.85


class SearchConfig(BaseModel):
    results_per_page: int = 50
    max_days_old_default: int = 14


class RateLimit(BaseModel):
    per_user_per_minute: int = 10


class AppConfig(BaseModel):
    search: SearchConfig = Field(default_factory=SearchConfig)
    scoring: Scoring = Field(default_factory=Scoring)
    timeouts: Timeouts = Field(default_factory=Timeouts)
    ratelimit: RateLimit = Field(default_factory=RateLimit)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str = ""
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_BASE_URL: str = "https://api.adzuna.com/v1/api/jobs"
    POSTGRES_DSN: str = "postgresql+psycopg://user:pass@localhost:5432/app"
    REDIS_URL: str = "redis://localhost:6379/0"
    TZ: str = "UTC"

    # In production the bot relies on Redis for distributed locks.
    # Allow falling back to an in-memory store only when explicitly enabled
    # (e.g. in tests or local development) to avoid multiple bot instances.
    ALLOW_IN_MEMORY_STORE: bool = True

    CONFIG_PATH: str = "config.yaml"


def load_app_config(path: str | Path) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return AppConfig.model_validate(data)

