from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("lang", sa.String(length=2), nullable=False),
        sa.Column("tz", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.Text()),
        sa.Column("skills", sa.JSON()),
        sa.Column("locations", sa.JSON()),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_max", sa.Integer()),
        sa.Column("formats", sa.JSON()),
        sa.Column("experience_yrs", sa.Integer()),
    )
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("redirect_url", sa.Text(), primary_key=True),
        sa.Column("added_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "blacklist_companies",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("company", sa.Text(), primary_key=True),
        sa.Column("added_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("kind", sa.Text(), primary_key=True),
        sa.Column("schedule_cron", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "applied",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("redirect_url", sa.Text(), primary_key=True),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("expire_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "shown_cache",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("vacancy_hash", sa.Text(), primary_key=True),
        sa.Column("shown_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "complaints",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("redirect_url", sa.Text(), primary_key=True),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True)),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("action", sa.Text()),
        sa.Column("payload", sa.JSON()),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("complaints")
    op.drop_table("shown_cache")
    op.drop_table("applied")
    op.drop_table("subscriptions")
    op.drop_table("blacklist_companies")
    op.drop_table("favorites")
    op.drop_table("profiles")
    op.drop_table("users")

