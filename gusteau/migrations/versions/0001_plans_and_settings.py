"""plans and settings

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
    )
    op.create_table(
        "plans",
        sa.Column("week", sa.String(8), primary_key=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week", sa.String(8), sa.ForeignKey("plans.week", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("slot", sa.String(20), nullable=False),
        sa.Column("recipe_slug", sa.String(120), nullable=False),
        sa.Column("recipe_title", sa.String(200), nullable=False),
        sa.UniqueConstraint("week", "day", "slot"),
    )
    op.create_index("ix_meals_week", "meals", ["week"])
    op.create_index("ix_meals_recipe_slug", "meals", ["recipe_slug"])


def downgrade() -> None:
    op.drop_table("meals")
    op.drop_table("plans")
    op.drop_table("settings")
