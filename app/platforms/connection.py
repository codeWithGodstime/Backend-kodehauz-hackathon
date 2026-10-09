"""Persist and look up workspace platform connections.

Connect stores the account identifiers an admin entered. It does not call Meta
and does not write ``access_token``. A production Meta app would fill that
column from OAuth (see the platform-connections endpoint docstring).
"""

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import PlatformConnection, PlatformConnectionStatus, PlatformName
from app.platforms.phone import normalize_phone

logger = logging.getLogger(__name__)


class PlatformConnectionError(ValueError):
    """The connect payload is missing an identifier for that platform."""


def connection_read(row: PlatformConnection) -> dict[str, Any]:
    """Public fields. ``access_token`` is intentionally omitted."""
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "platform": _enum_value(row.platform),
        "status": _enum_value(row.status),
        "display_phone_number": row.display_phone_number,
        "phone_number_id": row.phone_number_id,
        "page_id": row.page_id,
        "instagram_business_account_id": row.instagram_business_account_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_connections(session: Session, *, workspace_id: int) -> list[PlatformConnection]:
    return list(
        session.exec(
            select(PlatformConnection)
            .where(PlatformConnection.workspace_id == workspace_id)
            .order_by(PlatformConnection.id)
        ).all()
    )


def get_connection(
    session: Session, *, workspace_id: int, connection_id: int
) -> PlatformConnection | None:
    row = session.get(PlatformConnection, connection_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    return row


def connect_platform(
    session: Session,
    *,
    workspace_id: int,
    platform: str,
    display_phone_number: str | None = None,
    phone_number_id: str | None = None,
    page_id: str | None = None,
    instagram_business_account_id: str | None = None,
) -> PlatformConnection:
    """Create or update one platform row and mark it connected."""
    name = _require_platform(platform)
    fields = _identifiers(
        name,
        display_phone_number=display_phone_number,
        phone_number_id=phone_number_id,
        page_id=page_id,
        instagram_business_account_id=instagram_business_account_id,
    )
    existing = _find_platform(session, workspace_id=workspace_id, platform=name)
    if existing is None:
        row = PlatformConnection(
            workspace_id=workspace_id,
            platform=name,
            status=PlatformConnectionStatus.connected,
            access_token=None,
            **fields,
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = _find_platform(session, workspace_id=workspace_id, platform=name)
            if existing is None:
                raise
            return _apply_connect(session, existing, fields)
        session.refresh(row)
        logger.info(
            "platform connected workspace_id=%s platform=%s",
            workspace_id,
            name.value,
        )
        return row
    return _apply_connect(session, existing, fields)


def disconnect_platform(
    session: Session, *, workspace_id: int, connection_id: int
) -> PlatformConnection | None:
    row = get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    if row is None:
        return None
    row.status = PlatformConnectionStatus.disconnected
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info(
        "platform disconnected workspace_id=%s platform=%s",
        workspace_id,
        _enum_value(row.platform),
    )
    return row


def find_connected_whatsapp(
    session: Session,
    *,
    display_phone_number: str | None,
    phone_number_id: str | None,
) -> PlatformConnection | None:
    """Match a connected WhatsApp row by business number or phone number id."""
    phone = normalize_phone(display_phone_number)
    number_id = _clean(phone_number_id)
    if not phone and not number_id:
        return None
    rows = session.exec(
        select(PlatformConnection).where(
            PlatformConnection.platform == PlatformName.whatsapp,
            PlatformConnection.status == PlatformConnectionStatus.connected,
        )
    ).all()
    for row in rows:
        if phone and normalize_phone(row.display_phone_number) == phone:
            return row
        if number_id and _clean(row.phone_number_id) == number_id:
            return row
    return None


def _apply_connect(
    session: Session, row: PlatformConnection, fields: dict[str, str | None]
) -> PlatformConnection:
    row.status = PlatformConnectionStatus.connected
    for key, value in fields.items():
        setattr(row, key, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info(
        "platform connected workspace_id=%s platform=%s",
        row.workspace_id,
        _enum_value(row.platform),
    )
    return row


def _find_platform(
    session: Session, *, workspace_id: int, platform: PlatformName
) -> PlatformConnection | None:
    return session.exec(
        select(PlatformConnection).where(
            PlatformConnection.workspace_id == workspace_id,
            PlatformConnection.platform == platform,
        )
    ).first()


def _require_platform(platform: str) -> PlatformName:
    try:
        return PlatformName(str(platform).strip().lower())
    except ValueError as exc:
        raise PlatformConnectionError(
            "platform must be whatsapp, facebook, or instagram"
        ) from exc


def _identifiers(
    platform: PlatformName,
    *,
    display_phone_number: str | None,
    phone_number_id: str | None,
    page_id: str | None,
    instagram_business_account_id: str | None,
) -> dict[str, str | None]:
    phone = normalize_phone(display_phone_number)
    number_id = _clean(phone_number_id)
    page = _clean(page_id)
    instagram_id = _clean(instagram_business_account_id)
    if platform == PlatformName.whatsapp and not phone:
        raise PlatformConnectionError("display_phone_number is required for WhatsApp")
    if platform == PlatformName.facebook and not page:
        raise PlatformConnectionError("page_id is required for Facebook")
    if platform == PlatformName.instagram and not instagram_id:
        raise PlatformConnectionError(
            "instagram_business_account_id is required for Instagram"
        )
    return {
        "display_phone_number": phone,
        "phone_number_id": number_id,
        "page_id": page,
        "instagram_business_account_id": instagram_id,
    }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw)
