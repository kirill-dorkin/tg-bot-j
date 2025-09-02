from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def _alembic_config() -> Config:
    cfg = Config()
    # Point to our script location
    cfg.set_main_option("script_location", str(Path(__file__).parent))
    return cfg


def upgrade() -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")


def downgrade() -> None:
    cfg = _alembic_config()
    command.downgrade(cfg, "base")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.infra.migrations.run [upgrade|downgrade]")
        raise SystemExit(2)
    if sys.argv[1] == "upgrade":
        upgrade()
    elif sys.argv[1] == "downgrade":
        downgrade()
    else:
        raise SystemExit(2)

