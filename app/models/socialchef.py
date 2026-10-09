"""Socialchef billing cache, CRM customers, and ingested messages.

``Workspace`` is defined in msflib-workspaces and has no subscription columns.
Paystack renews the paid plan itself. This module stores the plan catalog and
each workspace's paid-until time.
"""

from datetime import datetime
from typing import Any

from msflib.models import BaseEnum, ModelBase
from msflib.workspaces.models.workspace import Workspace
from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, Relationship


class SubscriptionTier(BaseEnum):
    """Billing tier. Names match the values persisted by SQLAlchemy ``Enum``."""

    free = "free"
    paid = "paid"


FREE_PLAN_KEY = "free"
FREE_PLAN_NAME = "Socialchef Free"
PAID_MONTHLY_PLAN_KEY = "paid_monthly"
PAID_MONTHLY_PLAN_NAME = "Socialchef Paid Monthly"


class MessageCategory(BaseEnum):
    """Classification of an ingested message."""

    enquiry = "enquiry"
    order = "order"
    ignore = "ignore"


class PlatformName(BaseEnum):
    """Channel an admin can connect for a workspace.

    Values match the platforms the admin UI offers. Webhook ingress still uses
    ``channel_type`` ``whatsapp`` or ``meta``; Facebook and Instagram DMs share
    the Meta messaging webhook.
    """

    whatsapp = "whatsapp"
    facebook = "facebook"
    instagram = "instagram"


class PlatformConnectionStatus(BaseEnum):
    """Whether the workspace is treating this platform as connected."""

    connected = "connected"
    disconnected = "disconnected"


class SubscriptionPlan(ModelBase, table=True):
    """Catalog row shared by every workspace.

    The free plan has no Paystack plan code. The paid plan stores the code
    created by ``python -m app.seed.paystack_plans``.
    """

    __tablename__ = "subscription_plan"

    plan_key: str = Field(unique=True, index=True, max_length=64)
    name: str = Field(unique=True, max_length=255)
    tier: SubscriptionTier = Field(default=SubscriptionTier.paid)
    interval: str = Field(default="monthly", max_length=32)
    amount_kobo: int
    currency: str = Field(default="NGN", max_length=8)
    plan_code: str | None = Field(default=None, unique=True, index=True, max_length=64)


class WorkspaceSubscription(ModelBase, table=True):
    """Paid access for one workspace.

    Paystack charges the stored plan on its own schedule. This row records the
    plan code, customer, and local expiry. It does not trigger another charge.
    """

    __tablename__ = "workspace_subscription"

    workspace_id: int = Field(foreign_key="workspace.id", unique=True, index=True)
    tier: SubscriptionTier = Field(default=SubscriptionTier.free)
    subscription_expires_at: datetime | None = None
    plan_code: str | None = Field(default=None, index=True, max_length=64)
    gateway_customer_code: str | None = Field(default=None, index=True, max_length=255)
    gateway_customer_email: str | None = Field(default=None, max_length=255)
    authorization_code: str | None = Field(default=None, index=True, max_length=255)
    authorization_reusable: bool = Field(default=False)
    authorization_signature: str | None = Field(default=None, index=True, max_length=255)
    card_brand: str | None = Field(default=None, max_length=64)
    card_last4: str | None = Field(default=None, max_length=8)
    card_exp_month: str | None = Field(default=None, max_length=2)
    card_exp_year: str | None = Field(default=None, max_length=4)
    last_charge_reference: str | None = Field(default=None, unique=True, index=True, max_length=100)

    workspace: Workspace = Relationship()


class Customer(ModelBase, table=True):
    """CRM contact isolated to a single workspace.

    Phone and handle are unique per workspace when set. Database NULLs do not
    collide, so several customers may omit one of those fields.
    """

    __tablename__ = "customer"
    __table_args__ = (
        UniqueConstraint("workspace_id", "phone", name="uq_customer_workspace_phone"),
        UniqueConstraint("workspace_id", "handle", name="uq_customer_workspace_handle"),
    )

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str
    phone: str | None = None
    handle: str | None = None
    email: str | None = Field(default=None, index=True)

    workspace: Workspace = Relationship()
    messages: list["IngestedMessage"] = Relationship(back_populates="customer")


class IngestedMessage(ModelBase, table=True):
    """Raw inbound message plus classification metadata.

    The worker fills ``category`` and ``parsed_metadata``. Retries match
    ``workspace_id`` + ``channel_type`` + ``provider_message_id`` and do not
    insert a second row. ``timestamp`` is the source event time, separate
    from ``created_at``. ``display_phone_number`` is the WhatsApp business
    number the message was sent to (Cloud API ``metadata.display_phone_number``).
    """

    __tablename__ = "ingested_message"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "channel_type",
            "provider_message_id",
            name="uq_ingested_message_provider",
        ),
    )

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    channel_type: str = Field(max_length=32)
    provider_message_id: str = Field(max_length=512)
    sender: str | None = Field(default=None, max_length=255)
    display_phone_number: str | None = Field(default=None, index=True, max_length=32)
    customer_id: int | None = Field(default=None, foreign_key="customer.id", index=True)
    raw_payload: str = Field(sa_column=Column(Text, nullable=False))
    category: MessageCategory | None = Field(default=None, index=True)
    parsed_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    timestamp: datetime = Field(index=True)

    workspace: Workspace = Relationship()
    customer: Customer | None = Relationship(back_populates="messages")


class PlatformConnection(ModelBase, table=True):
    """One connected platform for a workspace.

    ``access_token`` is reserved for a real Meta token. Connect from the admin
    UI does not invent one, and API reads never return this column.
    ``display_phone_number`` and ``phone_number_id`` are the WhatsApp Cloud API
    metadata fields. ``page_id`` is the Facebook Page id. ``instagram_business_account_id``
    is the Instagram professional account id linked to that page.
    """

    __tablename__ = "platform_connection"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "platform",
            name="uq_platform_connection_workspace_platform",
        ),
    )

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    platform: PlatformName = Field(index=True)
    status: PlatformConnectionStatus = Field(
        default=PlatformConnectionStatus.disconnected,
        index=True,
    )
    display_phone_number: str | None = Field(default=None, index=True, max_length=32)
    phone_number_id: str | None = Field(default=None, index=True, max_length=64)
    page_id: str | None = Field(default=None, index=True, max_length=64)
    instagram_business_account_id: str | None = Field(default=None, index=True, max_length=64)
    access_token: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    workspace: Workspace = Relationship()
