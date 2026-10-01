"""shared shopping-list marks: in the cart, and the answer to "¿en casa?"

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopping_marks",
        sa.Column("week", sa.String(8), sa.ForeignKey("plans.week", ondelete="CASCADE"), primary_key=True),
        sa.Column("ingredient", sa.String(120), primary_key=True),
        sa.Column("in_cart", sa.Boolean(), nullable=False),
        sa.Column("at_home", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("shopping_marks")
