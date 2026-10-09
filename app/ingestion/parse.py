"""Normalize WhatsApp Cloud API and Meta Messenger/Instagram webhook payloads."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_CHANNELS = frozenset({"whatsapp", "meta"})

# Unix milliseconds are 13 digits; seconds are 10. Values above this are ms.
_MILLISECOND_THRESHOLD = 10_000_000_000


@dataclass(frozen=True)
class IncomingMessage:
    channel_type: str
    provider_message_id: str
    sender: str
    sender_name: str | None
    text: str
    timestamp: datetime
    raw_message: dict[str, Any]


def parse_incoming_messages(channel_type: str, payload: dict[str, Any]) -> list[IncomingMessage]:
    channel = channel_type.strip().lower()
    if channel == "whatsapp":
        return _parse_whatsapp(payload)
    if channel == "meta":
        return _parse_meta(payload)
    logger.warning("unsupported channel_type=%s", channel_type)
    return []


def _parse_whatsapp(payload: dict[str, Any]) -> list[IncomingMessage]:
    messages: list[IncomingMessage] = []
    for value in _whatsapp_values(payload):
        names = _whatsapp_contact_names(value)
        raw_messages = value.get("messages")
        if not isinstance(raw_messages, list):
            continue
        for raw in raw_messages:
            if not isinstance(raw, dict):
                continue
            message_id = _as_id(raw.get("id"))
            if message_id is None:
                logger.warning("whatsapp message missing id; skipping")
                continue
            sender = _as_id(raw.get("from")) or ""
            messages.append(
                IncomingMessage(
                    channel_type="whatsapp",
                    provider_message_id=message_id,
                    sender=sender,
                    sender_name=names.get(sender),
                    text=_whatsapp_text(raw),
                    timestamp=_parse_timestamp(raw.get("timestamp")),
                    raw_message=raw,
                )
            )
    return messages


def _parse_meta(payload: dict[str, Any]) -> list[IncomingMessage]:
    messages: list[IncomingMessage] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return messages
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        events = entry.get("messaging")
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            raw = event.get("message")
            if not isinstance(raw, dict) or raw.get("is_echo") is True:
                continue
            message_id = _as_id(raw.get("mid"))
            if message_id is None:
                logger.warning("meta message missing mid; skipping")
                continue
            sender_block = event.get("sender")
            sender = ""
            if isinstance(sender_block, dict):
                sender = _as_id(sender_block.get("id")) or ""
            text = raw.get("text") if isinstance(raw.get("text"), str) else ""
            messages.append(
                IncomingMessage(
                    channel_type="meta",
                    provider_message_id=message_id,
                    sender=sender,
                    sender_name=None,
                    text=text,
                    timestamp=_parse_timestamp(event.get("timestamp")),
                    raw_message=raw,
                )
            )
    return messages


def _whatsapp_values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return values
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if isinstance(value, dict):
                values.append(value)
    return values


def _whatsapp_contact_names(value: dict[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    contacts = value.get("contacts")
    if not isinstance(contacts, list):
        return names
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        wa_id = _as_id(contact.get("wa_id"))
        profile = contact.get("profile")
        if wa_id is None or not isinstance(profile, dict):
            continue
        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            names[wa_id] = name.strip()
    return names


def _whatsapp_text(raw: dict[str, Any]) -> str:
    message_type = raw.get("type")
    if message_type == "text":
        body = raw.get("text")
        if isinstance(body, dict) and isinstance(body.get("body"), str):
            return body["body"]
        return ""
    if message_type in {"image", "video", "document"}:
        media = raw.get(message_type)
        if isinstance(media, dict) and isinstance(media.get("caption"), str):
            return media["caption"]
        return ""
    if message_type == "button":
        button = raw.get("button")
        if isinstance(button, dict) and isinstance(button.get("text"), str):
            return button["text"]
        return ""
    if message_type == "interactive":
        interactive = raw.get("interactive")
        if not isinstance(interactive, dict):
            return ""
        for key in ("button_reply", "list_reply"):
            reply = interactive.get(key)
            if isinstance(reply, dict) and isinstance(reply.get("title"), str):
                return reply["title"]
    return ""


def _as_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _parse_timestamp(value: Any) -> datetime:
    number: float | None = None
    if isinstance(value, bool):
        number = None
    elif isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str) and value.strip().isdigit():
        number = float(value.strip())
    if number is None:
        return _utcnow()
    if number > _MILLISECOND_THRESHOLD:
        number = number / 1000
    return datetime.fromtimestamp(number, tz=timezone.utc).replace(tzinfo=None)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
