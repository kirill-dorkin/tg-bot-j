from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_ui_sessions_and_profile_ext"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users.full_name
    op.add_column("users", sa.Column("full_name", sa.Text(), nullable=True))
    # profiles.employment_types
    op.add_column("profiles", sa.Column("employment_types", sa.JSON(), nullable=True))
    # ui_sessions table
    op.create_table(
        "ui_sessions",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("anchor_message_id", sa.BigInteger(), nullable=True),
        sa.Column("screen_state", sa.String(length=64), nullable=False, server_default="welcome"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ui_sessions")
    op.drop_column("profiles", "employment_types")
    op.drop_column("users", "full_name")

