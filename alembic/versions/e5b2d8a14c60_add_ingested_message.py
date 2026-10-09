"""add customer and ingested message tables

Revision ID: e5b2d8a14c60
Revises: b7e3c91a4f20
Create Date: 2026-10-09 15:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5b2d8a14c60"
down_revision: str | None = "b7e3c91a4f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

message_category = postgresql.ENUM(
    "enquiry",
    "order",
    "ignore",
    name="messagecategory",
    create_type=False,
)


def _create_enum(name: str, labels: str) -> None:
    op.execute(
        f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_index(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == name for index in inspector.get_indexes(table))


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    _create_enum("messagecategory", "'enquiry', 'order', 'ignore'")

    if not _has_table("customer"):
        _create_customer()
    if not _has_table("ingested_message"):
        _create_ingested_message()
    else:
        _ensure_message_columns()


def _create_customer() -> None:
    op.create_table(
        "customer",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("handle", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_workspace_id", "customer", ["workspace_id"], unique=False)
    op.create_index("ix_customer_email", "customer", ["email"], unique=False)
    op.create_index(
        "uq_customer_workspace_phone",
        "customer",
        ["workspace_id", "phone"],
        unique=True,
    )
    op.create_index(
        "uq_customer_workspace_handle",
        "customer",
        ["workspace_id", "handle"],
        unique=True,
    )


def _create_ingested_message() -> None:
    op.create_table(
        "ingested_message",
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
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=512), nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("category", message_category, nullable=True),
        sa.Column("parsed_metadata", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingested_message_workspace_id",
        "ingested_message",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingested_message_customer_id",
        "ingested_message",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingested_message_category",
        "ingested_message",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_ingested_message_timestamp",
        "ingested_message",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        "uq_ingested_message_provider",
        "ingested_message",
        ["workspace_id", "channel_type", "provider_message_id"],
        unique=True,
    )


def _ensure_message_columns() -> None:
    columns = _column_names("ingested_message")
    if "channel_type" not in columns:
        op.add_column(
            "ingested_message",
            sa.Column("channel_type", sa.String(length=32), nullable=True),
        )
        op.execute("UPDATE ingested_message SET channel_type = '' WHERE channel_type IS NULL")
        op.alter_column("ingested_message", "channel_type", nullable=False)
    if "provider_message_id" not in columns:
        op.add_column(
            "ingested_message",
            sa.Column("provider_message_id", sa.String(length=512), nullable=True),
        )
        op.execute(
            "UPDATE ingested_message SET provider_message_id = '' "
            "WHERE provider_message_id IS NULL"
        )
        op.alter_column("ingested_message", "provider_message_id", nullable=False)
    if "sender" not in columns:
        op.add_column(
            "ingested_message",
            sa.Column("sender", sa.String(length=255), nullable=True),
        )
    if not _has_index("ingested_message", "uq_ingested_message_provider"):
        op.create_index(
            "uq_ingested_message_provider",
            "ingested_message",
            ["workspace_id", "channel_type", "provider_message_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_ingested_message_provider", table_name="ingested_message")
    op.drop_index("ix_ingested_message_timestamp", table_name="ingested_message")
    op.drop_index("ix_ingested_message_category", table_name="ingested_message")
    op.drop_index("ix_ingested_message_customer_id", table_name="ingested_message")
    op.drop_index("ix_ingested_message_workspace_id", table_name="ingested_message")
    op.drop_table("ingested_message")
    op.drop_index("uq_customer_workspace_handle", table_name="customer")
    op.drop_index("uq_customer_workspace_phone", table_name="customer")
    op.drop_index("ix_customer_email", table_name="customer")
    op.drop_index("ix_customer_workspace_id", table_name="customer")
    op.drop_table("customer")
    op.execute("DROP TYPE IF EXISTS messagecategory")
