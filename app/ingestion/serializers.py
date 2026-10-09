"""API-facing shapes for ingested messages."""

import json
from typing import Any

from app.ingestion.parse import _whatsapp_text
from app.models import Customer, IngestedMessage


def message_body_from_raw(raw_payload: str) -> str:
    try:
        loaded = json.loads(raw_payload)
    except json.JSONDecodeError:
        return ""
    if isinstance(loaded, dict):
        text = _whatsapp_text(loaded)
        if text:
            return text
        body = loaded.get("body")
        if isinstance(body, str):
            return body
    return ""


def ingested_message_read(
    row: IngestedMessage,
    *,
    customer: Customer | None = None,
) -> dict[str, Any]:
    category = row.category
    category_value = (
        str(getattr(category, "value", category)) if category is not None else None
    )
    linked = customer
    if linked is None and row.customer_id is not None:
        linked = row.customer
    customer_name = linked.name if linked is not None else None
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "channel_type": row.channel_type,
        "provider_message_id": row.provider_message_id,
        "sender": row.sender,
        "customer_name": customer_name,
        "display_phone_number": row.display_phone_number,
        "category": category_value,
        "body": message_body_from_raw(row.raw_payload),
        "parsed_metadata": row.parsed_metadata,
        "timestamp": row.timestamp,
        "created_at": row.created_at,
    }
