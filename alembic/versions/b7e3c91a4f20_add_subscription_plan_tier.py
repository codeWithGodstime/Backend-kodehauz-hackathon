"""add tier to subscription plan

Revision ID: b7e3c91a4f20
Revises: c4a8e1b27d30
Create Date: 2026-10-09 14:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e3c91a4f20"
down_revision: Union[str, None] = "c4a8e1b27d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscription_tier = postgresql.ENUM("free", "paid", name="subscriptiontier", create_type=False)


def upgrade() -> None:
    op.add_column(
        "subscription_plan",
        sa.Column(
            "tier",
            subscription_tier,
            nullable=False,
            server_default=sa.text("'paid'::subscriptiontier"),
        ),
    )
    op.alter_column("subscription_plan", "tier", server_default=None)


def downgrade() -> None:
    op.drop_column("subscription_plan", "tier")
