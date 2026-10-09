"""add platform connection and message destination number

Revision ID: f1a9c3e87b21
Revises: e5b2d8a14c60
Create Date: 2026-10-09 16:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f1a9c3e87b21"
down_revision: str | None = "e5b2d8a14c60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

platform_name = postgresql.ENUM(
    "whatsapp",
    "facebook",
    "instagram",
    name="platformname",
    create_type=False,
)
platform_connection_status = postgresql.ENUM(
    "connected",
    "disconnected",
    name="platformconnectionstatus",
    create_type=False,
)


def _create_enum(name: str, labels: str) -> None:
    op.execute(
        f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    _create_enum("platformname", "'whatsapp', 'facebook', 'instagram'")
    _create_enum("platformconnectionstatus", "'connected', 'disconnected'")

    if _has_table("ingested_message"):
        columns = _column_names("ingested_message")
        if "display_phone_number" not in columns:
            op.add_column(
                "ingested_message",
                sa.Column("display_phone_number", sa.String(length=32), nullable=True),
            )
            op.create_index(
                "ix_ingested_message_display_phone_number",
                "ingested_message",
                ["display_phone_number"],
                unique=False,
            )

    if not _has_table("platform_connection"):
        op.create_table(
            "platform_connection",
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
            sa.Column("platform", platform_name, nullable=False),
            sa.Column("status", platform_connection_status, nullable=False),
            sa.Column("display_phone_number", sa.String(length=32), nullable=True),
            sa.Column("phone_number_id", sa.String(length=64), nullable=True),
            sa.Column("page_id", sa.String(length=64), nullable=True),
            sa.Column("instagram_business_account_id", sa.String(length=64), nullable=True),
            sa.Column("access_token", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workspace_id",
                "platform",
                name="uq_platform_connection_workspace_platform",
            ),
        )
        op.create_index(
            "ix_platform_connection_workspace_id",
            "platform_connection",
            ["workspace_id"],
            unique=False,
        )
        op.create_index(
            "ix_platform_connection_platform",
            "platform_connection",
            ["platform"],
            unique=False,
        )
        op.create_index(
            "ix_platform_connection_status",
            "platform_connection",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_platform_connection_display_phone_number",
            "platform_connection",
            ["display_phone_number"],
            unique=False,
        )
        op.create_index(
            "ix_platform_connection_phone_number_id",
            "platform_connection",
            ["phone_number_id"],
            unique=False,
        )
        op.create_index(
            "ix_platform_connection_page_id",
            "platform_connection",
            ["page_id"],
            unique=False,
        )
        op.create_index(
            "ix_platform_connection_instagram_business_account_id",
            "platform_connection",
            ["instagram_business_account_id"],
            unique=False,
        )


def downgrade() -> None:
    if _has_table("platform_connection"):
        op.drop_index(
            "ix_platform_connection_instagram_business_account_id",
            table_name="platform_connection",
        )
        op.drop_index("ix_platform_connection_page_id", table_name="platform_connection")
        op.drop_index(
            "ix_platform_connection_phone_number_id",
            table_name="platform_connection",
        )
        op.drop_index(
            "ix_platform_connection_display_phone_number",
            table_name="platform_connection",
        )
        op.drop_index("ix_platform_connection_status", table_name="platform_connection")
        op.drop_index("ix_platform_connection_platform", table_name="platform_connection")
        op.drop_index(
            "ix_platform_connection_workspace_id",
            table_name="platform_connection",
        )
        op.drop_table("platform_connection")
    if _has_table("ingested_message") and "display_phone_number" in _column_names(
        "ingested_message"
    ):
        op.drop_index(
            "ix_ingested_message_display_phone_number",
            table_name="ingested_message",
        )
        op.drop_column("ingested_message", "display_phone_number")
    op.execute("DROP TYPE IF EXISTS platformconnectionstatus")
    op.execute("DROP TYPE IF EXISTS platformname")
