"""Persist normalized webhook messages. Idempotent on the provider message id."""

import json
import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.ingestion.classify import classify_message
from app.ingestion.parse import SUPPORTED_CHANNELS, IncomingMessage, parse_incoming_messages
from app.models import Customer, IngestedMessage, Workspace

logger = logging.getLogger(__name__)


def process_incoming_message(
    session: Session,
    *,
    workspace_id: int,
    channel_type: str,
    raw_payload: Any,
) -> dict[str, Any]:
    """Parse, classify, and store every message in one webhook payload."""
    channel = channel_type.strip().lower()
    if channel not in SUPPORTED_CHANNELS:
        logger.warning("ignoring unsupported channel_type=%s", channel_type)
        return {"status": "ignored", "ingested_message_ids": []}

    try:
        payload = _coerce_payload(raw_payload)
    except ValueError:
        logger.warning(
            "ignoring malformed payload workspace_id=%s channel_type=%s",
            workspace_id,
            channel,
        )
        return {"status": "ignored", "ingested_message_ids": []}

    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        logger.warning("workspace %s not found; skipping payload", workspace_id)
        return {"status": "ignored", "ingested_message_ids": []}

    try:
        incoming = parse_incoming_messages(channel, payload)
    except Exception:
        logger.exception(
            "failed to parse payload workspace_id=%s channel_type=%s",
            workspace_id,
            channel,
        )
        return {"status": "ignored", "ingested_message_ids": []}

    if not incoming:
        logger.info(
            "no inbound messages workspace_id=%s channel_type=%s",
            workspace_id,
            channel,
        )
        return {"status": "ignored", "ingested_message_ids": []}

    ids: list[int] = []
    for message in incoming:
        try:
            row = persist_incoming_message(
                session,
                workspace_id=workspace_id,
                message=message,
            )
        except Exception:
            logger.exception(
                "failed to persist provider_message_id=%s",
                message.provider_message_id,
            )
            session.rollback()
            continue
        if row.id is not None:
            ids.append(row.id)
    status = "ok" if ids else "ignored"
    return {"status": status, "ingested_message_ids": ids}


def persist_incoming_message(
    session: Session,
    *,
    workspace_id: int,
    message: IncomingMessage,
) -> IngestedMessage:
    existing = _find_existing(session, workspace_id=workspace_id, message=message)
    if existing is not None:
        return existing

    extraction = classify_message(message.text, session=session, workspace_id=workspace_id)
    customer = _customer_for(session, workspace_id=workspace_id, message=message)
    row = IngestedMessage(
        workspace_id=workspace_id,
        channel_type=message.channel_type,
        provider_message_id=message.provider_message_id,
        sender=message.sender or None,
        customer_id=customer.id if customer is not None else None,
        raw_payload=json.dumps(message.raw_message, ensure_ascii=False, default=str),
        category=extraction.message_category(),
        parsed_metadata=extraction.parsed_metadata(),
        timestamp=message.timestamp,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find_existing(session, workspace_id=workspace_id, message=message)
        if existing is not None:
            return existing
        raise
    session.refresh(row)
    logger.info(
        "ingested message id=%s workspace_id=%s channel=%s category=%s provider_message_id=%s",
        row.id,
        workspace_id,
        message.channel_type,
        row.category,
        message.provider_message_id,
    )
    return row


def _find_existing(
    session: Session,
    *,
    workspace_id: int,
    message: IncomingMessage,
) -> IngestedMessage | None:
    return session.exec(
        select(IngestedMessage).where(
            IngestedMessage.workspace_id == workspace_id,
            IngestedMessage.channel_type == message.channel_type,
            IngestedMessage.provider_message_id == message.provider_message_id,
        )
    ).first()


def _customer_for(
    session: Session,
    *,
    workspace_id: int,
    message: IncomingMessage,
) -> Customer | None:
    if not message.sender:
        return None
    phone = message.sender if message.channel_type == "whatsapp" else None
    handle = message.sender if message.channel_type == "meta" else None
    existing = _find_customer(session, workspace_id=workspace_id, phone=phone, handle=handle)
    if existing is not None:
        return existing

    customer = Customer(
        workspace_id=workspace_id,
        name=message.sender_name or message.sender,
        phone=phone,
        handle=handle,
    )
    session.add(customer)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = _find_customer(session, workspace_id=workspace_id, phone=phone, handle=handle)
        if existing is not None:
            return existing
        raise
    return customer


def _find_customer(
    session: Session,
    *,
    workspace_id: int,
    phone: str | None,
    handle: str | None,
) -> Customer | None:
    if phone:
        found = session.exec(
            select(Customer).where(Customer.workspace_id == workspace_id, Customer.phone == phone)
        ).first()
        if found is not None:
            return found
    if handle:
        return session.exec(
            select(Customer).where(
                Customer.workspace_id == workspace_id,
                Customer.handle == handle,
            )
        ).first()
    return None


def _coerce_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        try:
            loaded = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("payload is not JSON") from exc
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("payload is not a JSON object")
