"""WhatsApp and Meta webhook ingress. Classification runs in Celery, not here."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from app.api import deps
from app.core.config import settings
from app.ingestion.parse import SUPPORTED_CHANNELS, whatsapp_destination
from app.ingestion.signature import signatures_match, verify_tokens_match
from app.models import Workspace
from app.platforms.connection import find_connected_whatsapp
from app.worker import process_incoming_message_task

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_channel(channel_type: str) -> str:
    channel = channel_type.strip().lower()
    if channel not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=422, detail="Unsupported channel")
    return channel


def _require_workspace(session: Session, workspace_id: int) -> None:
    if session.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")


async def _signed_payload(request: Request) -> dict[str, Any]:
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not signatures_match(body, signature, settings.META_APP_SECRET):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook body is not JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")
    return payload


def _enqueue(workspace_id: int, channel: str, payload: dict[str, Any]) -> dict[str, str]:
    process_incoming_message_task.delay(
        workspace_id=workspace_id,
        channel_type=channel,
        raw_payload=payload,
    )
    logger.info("queued webhook workspace_id=%s channel_type=%s", workspace_id, channel)
    return {"status": "accepted"}


@router.get("/{channel_type}/{workspace_id}")
def verify_webhook(
    channel_type: str,
    workspace_id: int,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    session: Session = Depends(deps.get_session),
) -> PlainTextResponse:
    """Meta hub challenge. Echo ``hub.challenge`` when the verify token matches."""
    _require_channel(channel_type)
    expected = settings.META_WEBHOOK_VERIFY_TOKEN
    token_ok = verify_tokens_match(hub_verify_token, expected)
    if hub_mode != "subscribe" or not token_ok:
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    _require_workspace(session, workspace_id)
    return PlainTextResponse(content=hub_challenge)


@router.post("/{channel_type}/inbound")
async def receive_webhook_for_connected_number(
    channel_type: str,
    request: Request,
    session: Session = Depends(deps.get_session),
) -> dict[str, str]:
    """Resolve the workspace from the WhatsApp number the message was sent to.

    ``metadata.display_phone_number`` and ``metadata.phone_number_id`` must
    match a connected WhatsApp platform row. This is the URL the local
    simulator posts to.
    """
    channel = _require_channel(channel_type)
    if channel != "whatsapp":
        raise HTTPException(
            status_code=422,
            detail="Only WhatsApp can be resolved from a connected number",
        )
    payload = await _signed_payload(request)
    phone, number_id = whatsapp_destination(payload)
    if not phone and not number_id:
        raise HTTPException(
            status_code=422,
            detail="Webhook metadata is missing display_phone_number and phone_number_id",
        )
    connection = find_connected_whatsapp(
        session,
        display_phone_number=phone,
        phone_number_id=number_id,
    )
    if connection is None or connection.workspace_id is None:
        raise HTTPException(status_code=404, detail="No connected WhatsApp number")
    return _enqueue(connection.workspace_id, channel, payload)


@router.post("/{channel_type}/{workspace_id}")
async def receive_webhook(
    channel_type: str,
    workspace_id: int,
    request: Request,
    session: Session = Depends(deps.get_session),
) -> dict[str, str]:
    """Verify the raw body, acknowledge, and hand the payload to Celery."""
    channel = _require_channel(channel_type)
    payload = await _signed_payload(request)
    _require_workspace(session, workspace_id)
    if channel == "whatsapp":
        phone, number_id = whatsapp_destination(payload)
        if phone or number_id:
            connection = find_connected_whatsapp(
                session,
                display_phone_number=phone,
                phone_number_id=number_id,
            )
            if connection is not None and connection.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=409,
                    detail="WhatsApp number is connected to a different workspace",
                )
    return _enqueue(workspace_id, channel, payload)
