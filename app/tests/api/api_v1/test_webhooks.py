"""Webhook ingress: hub challenge, HMAC, and Celery handoff."""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Workspace

SECRET = "test-meta-secret"
TOKEN = "test-verify-token"


def _workspace_id(session: Session) -> int:
    workspace = session.exec(select(Workspace)).first()
    assert workspace is not None
    assert workspace.id is not None
    return workspace.id


def _sign(body: bytes) -> str:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_hub_challenge_accepts_verify_token(
    client: TestClient, session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", TOKEN)
    workspace_id = _workspace_id(session)
    response = client.get(
        f"{settings.API_V1_STR}/webhooks/whatsapp/{workspace_id}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": TOKEN,
            "hub.challenge": "challenge-token-99",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge-token-99"


def test_hub_challenge_rejects_bad_token(
    client: TestClient, session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", TOKEN)
    workspace_id = _workspace_id(session)
    response = client.get(
        f"{settings.API_V1_STR}/webhooks/meta/{workspace_id}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge-token-99",
        },
    )
    assert response.status_code == 403


def test_post_rejects_bad_signature(
    client: TestClient, session: Session, monkeypatch, mocker
) -> None:
    monkeypatch.setattr(settings, "META_APP_SECRET", SECRET)
    delay = mocker.patch("app.api.api_v1.endpoints.webhooks.process_incoming_message_task.delay")
    workspace_id = _workspace_id(session)
    body = json.dumps({"object": "page"}).encode()
    response = client.post(
        f"{settings.API_V1_STR}/webhooks/meta/{workspace_id}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert response.status_code == 403
    delay.assert_not_called()


def test_post_valid_signature_enqueues_task(
    client: TestClient, session: Session, monkeypatch, mocker
) -> None:
    monkeypatch.setattr(settings, "META_APP_SECRET", SECRET)
    delay = mocker.patch("app.api.api_v1.endpoints.webhooks.process_incoming_message_task.delay")
    workspace_id = _workspace_id(session)
    payload = {"object": "whatsapp_business_account", "entry": []}
    body = json.dumps(payload).encode()
    response = client.post(
        f"{settings.API_V1_STR}/webhooks/whatsapp/{workspace_id}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    delay.assert_called_once_with(
        workspace_id=workspace_id,
        channel_type="whatsapp",
        raw_payload=payload,
    )
