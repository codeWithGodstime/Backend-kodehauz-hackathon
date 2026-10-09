"""Inbound WhatsApp webhook resolves the workspace from the business number."""

import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.platforms.connection import connect_platform
from app.seed.demo import BUSINESS_DISPLAY_PHONE_NUMBER, BUSINESS_PHONE_NUMBER_ID
from app.tests.api.api_v1.test_dashboard import _owned_workspace
from app.tests.api.api_v1.test_webhooks import SECRET, _sign
from scripts.simulate_whatsapp_webhook import MESSAGES, webhook_payload


def test_inbound_webhook_queues_for_connected_number(
    client: TestClient, session: Session, monkeypatch, mocker
) -> None:
    monkeypatch.setattr(settings, "META_APP_SECRET", SECRET)
    delay = mocker.patch("app.api.api_v1.endpoints.webhooks.process_incoming_message_task.delay")
    _, workspace = _owned_workspace(session)
    connect_platform(
        session,
        workspace_id=workspace.id,
        platform="whatsapp",
        display_phone_number=BUSINESS_DISPLAY_PHONE_NUMBER,
        phone_number_id=BUSINESS_PHONE_NUMBER_ID,
    )
    payload = webhook_payload(MESSAGES[0], index=0)
    body = json.dumps(payload).encode()
    response = client.post(
        f"{settings.API_V1_STR}/webhooks/whatsapp/inbound",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    delay.assert_called_once_with(
        workspace_id=workspace.id,
        channel_type="whatsapp",
        raw_payload=payload,
    )


def test_inbound_webhook_404_when_number_is_not_connected(
    client: TestClient, session: Session, monkeypatch, mocker
) -> None:
    monkeypatch.setattr(settings, "META_APP_SECRET", SECRET)
    delay = mocker.patch("app.api.api_v1.endpoints.webhooks.process_incoming_message_task.delay")
    payload = webhook_payload(MESSAGES[1], index=1)
    body = json.dumps(payload).encode()
    response = client.post(
        f"{settings.API_V1_STR}/webhooks/whatsapp/inbound",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 404
    delay.assert_not_called()
    assert session is not None
