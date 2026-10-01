"""meal outcomes and purchases

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("meals") as batch:
        batch.add_column(sa.Column("status", sa.String(10), nullable=True))
        batch.add_column(sa.Column("swap_slug", sa.String(120), nullable=True))
        batch.add_column(sa.Column("swap_title", sa.String(200), nullable=True))
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week", sa.String(8), sa.ForeignKey("plans.week", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("people", sa.Integer(), nullable=False),
        sa.Column("estimated_total", sa.Float(), nullable=True),
        sa.Column("actual_total", sa.Float(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
    )
    op.create_index("ix_purchases_week", "purchases", ["week"])


def downgrade() -> None:
    op.drop_table("purchases")
    with op.batch_alter_table("meals") as batch:
        batch.drop_column("swap_title")
        batch.drop_column("swap_slug")
        batch.drop_column("status")
