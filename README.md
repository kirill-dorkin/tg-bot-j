# Adzuna Job Bot

Production-grade Telegram bot for job matching using Adzuna as the only source. Built with aiogram 3, PostgreSQL, Redis, and a ranking pipeline.

- Language: Python 3.11+
- Telegram: aiogram 3.x (FSM)
- DB: PostgreSQL 15 via SQLAlchemy 2.x + Alembic
- Cache/Keys: Redis 7
- HTTP: httpx
- Config: pydantic-settings (.env + config.yaml)
- Logging: structlog + loguru
- Tests: pytest + pytest-asyncio + httpx-mock
- Docker + docker-compose

See `config.yaml` and `.env.example` for settings.

## Commands
- make dev — start postgres/redis, run migrations, run bot
  
  Prereq: Docker installed. On macOS, `make dev` will attempt to auto-start Docker Desktop if the daemon isn’t running.

- make test — run tests
- make up — production containers

## Notes
- Source of data MUST be Adzuna only.
- UI produces strict JSON cards from the pipeline.
- No secrets are ever logged.
