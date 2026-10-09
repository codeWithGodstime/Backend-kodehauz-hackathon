"""Idempotent demo workspace: dev user, members, and the WhatsApp business line.

Called from ``python -m app.initial_data`` (also the Docker prestart path).
Re-running does not create a second workspace or a second membership.

Phone numbers are digits only, matching WhatsApp Cloud API ``wa_id`` values.
``account.phone`` is the person's WhatsApp number. The business line customers
message is ``BUSINESS_DISPLAY_PHONE_NUMBER`` on the connected platform row.
"""

import logging

from sqlmodel import Session

from app.actions import account_action, user_action, workspace_action
from app.core.config import settings
from app.models import (
    AccountCreate,
    AccountRole,
    AccountStatus,
    AccountUpdate,
    PlatformName,
    ProfileCreate,
    UserType,
)
from app.platforms.connection import connect_platform, list_connections
from app.platforms.phone import normalize_phone

logger = logging.getLogger(__name__)

BUSINESS_DISPLAY_PHONE_NUMBER = "2348095550100"
BUSINESS_PHONE_NUMBER_ID = "106855512345678"
DEV_USER_PHONE = "2348011110001"
MEMBER_PASSWORD = "seedpass123"

MEMBERS: tuple[dict[str, str], ...] = (
    {
        "email": "member.ada@socialchef.example",
        "username": "member.ada",
        "phone": "2348022220002",
        "first_name": "Ada",
        "last_name": "Okoye",
    },
    {
        "email": "member.bola@socialchef.example",
        "username": "member.bola",
        "phone": "2348033330003",
        "first_name": "Bola",
        "last_name": "Adeyemi",
    },
)


def ensure_socialchef_seed(session: Session) -> None:
    """Attach the dev user and members to the existing default workspace."""
    account = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    if account is None or account.id is None:
        logger.warning("skipping socialchef seed; dev user %s is missing", settings.FIRST_SUPERUSER)
        return

    _ensure_phone(session, account, DEV_USER_PHONE)
    workspace = _workspace_for(session, account)
    if workspace is None or workspace.id is None:
        logger.warning("skipping socialchef seed; dev user has no workspace")
        return

    user_action.create_membership(
        session,
        account_id=account.id,
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        membership_type=UserType.owner,
        commit=False,
    )
    for spec in MEMBERS:
        _ensure_member(session, workspace=workspace, spec=spec)

    session.commit()
    _ensure_whatsapp_connection(session, workspace_id=workspace.id)
    logger.info(
        "socialchef seed workspace_id=%s slug=%s business_display_phone_number=%s",
        workspace.id,
        workspace.slug,
        BUSINESS_DISPLAY_PHONE_NUMBER,
    )


def _ensure_phone(session: Session, account, phone: str) -> None:
    current = normalize_phone(account.phone) or ""
    if current:
        return
    account_action.update(
        session,
        model=account,
        data=AccountUpdate(phone=phone),
        commit=False,
    )


def _workspace_for(session: Session, account):
    if account.current_workspace_id is not None:
        from app.models import Workspace

        workspace = session.get(Workspace, account.current_workspace_id)
        if workspace is not None:
            return workspace
    rows = workspace_action.get_multi_by_all(session, owner_id=account.id, limit=1)
    return rows[0] if rows else None


def _ensure_member(session: Session, *, workspace, spec: dict[str, str]) -> None:
    account = account_action.get_by_email(session, email=spec["email"])
    if account is None:
        account = account_action.create(
            session,
            data=AccountCreate(
                username=spec["username"],
                email=spec["email"],
                phone=spec["phone"],
                password=MEMBER_PASSWORD,
                status=AccountStatus.active,
                role=AccountRole.user,
                profile=ProfileCreate(
                    first_name=spec["first_name"],
                    last_name=spec["last_name"],
                ),
            ),
            commit=False,
        )
    else:
        _ensure_phone(session, account, spec["phone"])

    if account.id is None:
        return
    membership = user_action.create_membership(
        session,
        account_id=account.id,
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        membership_type=UserType.member,
        commit=False,
    )
    display_name = f"{spec['first_name']} {spec['last_name']}"
    if not membership.display_name:
        membership.display_name = display_name
        session.add(membership)
    if account.current_workspace_id is None:
        account.current_workspace_id = workspace.id
        session.add(account)


def _ensure_whatsapp_connection(session: Session, *, workspace_id: int) -> None:
    for row in list_connections(session, workspace_id=workspace_id):
        if str(getattr(row.platform, "value", row.platform)) == PlatformName.whatsapp.value:
            return
    connect_platform(
        session,
        workspace_id=workspace_id,
        platform=PlatformName.whatsapp.value,
        display_phone_number=BUSINESS_DISPLAY_PHONE_NUMBER,
        phone_number_id=BUSINESS_PHONE_NUMBER_ID,
    )
