"""add subscription plan and billing tables

Revision ID: c4a8e1b27d30
Revises:
Create Date: 2026-10-09 13:59:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a8e1b27d30"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscription_tier = postgresql.ENUM("free", "paid", name="subscriptiontier", create_type=False)
payment_status = postgresql.ENUM(
    "verified",
    "unverified",
    "failed",
    "fulfilled",
    name="paymentstatus",
    create_type=False,
)
payment_gateway = postgresql.ENUM(
    "stripe", "paystack", name="paymentgateway", create_type=False
)
payment_queue_status = postgresql.ENUM(
    "queued", "processed", name="paymentqueuestatus", create_type=False
)


def _create_enum(name: str, labels: str) -> None:
    op.execute(
        f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )


def upgrade() -> None:
    _create_enum("subscriptiontier", "'free', 'paid'")
    _create_enum("paymentstatus", "'verified', 'unverified', 'failed', 'fulfilled'")
    _create_enum("paymentgateway", "'stripe', 'paystack'")
    _create_enum("paymentqueuestatus", "'queued', 'processed'")

    op.create_table(
        "subscription_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("plan_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("interval", sa.String(length=32), nullable=False),
        sa.Column("amount_kobo", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("plan_code", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_subscription_plan_plan_key", "subscription_plan", ["plan_key"], unique=True
    )
    op.create_index(
        "ix_subscription_plan_plan_code", "subscription_plan", ["plan_code"], unique=True
    )

    op.create_table(
        "workspace_subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("tier", subscription_tier, nullable=False),
        sa.Column("subscription_expires_at", sa.DateTime(), nullable=True),
        sa.Column("plan_code", sa.String(length=64), nullable=True),
        sa.Column("gateway_customer_code", sa.String(length=255), nullable=True),
        sa.Column("gateway_customer_email", sa.String(length=255), nullable=True),
        sa.Column("authorization_code", sa.String(length=255), nullable=True),
        sa.Column("authorization_reusable", sa.Boolean(), nullable=False),
        sa.Column("authorization_signature", sa.String(length=255), nullable=True),
        sa.Column("card_brand", sa.String(length=64), nullable=True),
        sa.Column("card_last4", sa.String(length=8), nullable=True),
        sa.Column("card_exp_month", sa.String(length=2), nullable=True),
        sa.Column("card_exp_year", sa.String(length=4), nullable=True),
        sa.Column("last_charge_reference", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspace_subscription_workspace_id",
        "workspace_subscription",
        ["workspace_id"],
        unique=True,
    )
    op.create_index(
        "ix_workspace_subscription_plan_code",
        "workspace_subscription",
        ["plan_code"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_subscription_gateway_customer_code",
        "workspace_subscription",
        ["gateway_customer_code"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_subscription_authorization_code",
        "workspace_subscription",
        ["authorization_code"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_subscription_authorization_signature",
        "workspace_subscription",
        ["authorization_signature"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_subscription_last_charge_reference",
        "workspace_subscription",
        ["last_charge_reference"],
        unique=True,
    )

    op.create_table(
        "payment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("callback_url", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("authorization_url", sa.String(), nullable=False),
        sa.Column("access_code", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("gateway", payment_gateway, nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paymentqueue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("status", payment_queue_status, nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("paymentqueue")
    op.drop_table("payment")
    op.drop_index(
        "ix_workspace_subscription_last_charge_reference",
        table_name="workspace_subscription",
    )
    op.drop_index(
        "ix_workspace_subscription_authorization_signature",
        table_name="workspace_subscription",
    )
    op.drop_index(
        "ix_workspace_subscription_authorization_code",
        table_name="workspace_subscription",
    )
    op.drop_index(
        "ix_workspace_subscription_gateway_customer_code",
        table_name="workspace_subscription",
    )
    op.drop_index(
        "ix_workspace_subscription_plan_code", table_name="workspace_subscription"
    )
    op.drop_index(
        "ix_workspace_subscription_workspace_id", table_name="workspace_subscription"
    )
    op.drop_table("workspace_subscription")
    op.drop_index("ix_subscription_plan_plan_code", table_name="subscription_plan")
    op.drop_index("ix_subscription_plan_plan_key", table_name="subscription_plan")
    op.drop_table("subscription_plan")
    op.execute("DROP TYPE IF EXISTS paymentqueuestatus")
    op.execute("DROP TYPE IF EXISTS paymentgateway")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS subscriptiontier")
