"""Owner and admin can connect a platform. Reads never include access_token."""

from fastapi.testclient import TestClient
from msflib.utils.tests.account import create_random_account_with_token
from sqlmodel import Session

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import PlatformConnection, UserType
from app.tests.api.api_v1.test_dashboard import _owned_workspace


def _url(slug: str, suffix: str = "") -> str:
    return f"{settings.API_V1_STR}/{slug}/platform-connections{suffix}"


def test_owner_connects_whatsapp_and_disconnects(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    response = client.post(
        _url(workspace.slug),
        headers=superuser_account_token_headers,
        json={
            "platform": "whatsapp",
            "display_phone_number": "+234 809 555 0100",
            "phone_number_id": "106855512345678",
            "access_token": "should-not-be-stored",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "whatsapp"
    assert body["status"] == "connected"
    assert body["display_phone_number"] == "2348095550100"
    assert body["phone_number_id"] == "106855512345678"
    assert "access_token" not in body

    stored = session.get(PlatformConnection, body["id"])
    assert stored is not None
    assert stored.access_token is None

    again = client.post(
        _url(workspace.slug),
        headers=superuser_account_token_headers,
        json={
            "platform": "whatsapp",
            "display_phone_number": "2348095550100",
            "phone_number_id": "106855512345678",
        },
    )
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]

    listed = client.get(_url(workspace.slug), headers=superuser_account_token_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    disconnected = client.post(
        _url(workspace.slug, f"/{body['id']}/disconnect"),
        headers=superuser_account_token_headers,
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["status"] == "disconnected"


def test_connect_requires_platform_identifier(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    missing = client.post(
        _url(workspace.slug),
        headers=superuser_account_token_headers,
        json={"platform": "facebook"},
    )
    assert missing.status_code == 422
    facebook = client.post(
        _url(workspace.slug),
        headers=superuser_account_token_headers,
        json={"platform": "facebook", "page_id": "111222333"},
    )
    assert facebook.status_code == 200
    assert facebook.json()["page_id"] == "111222333"
    instagram = client.post(
        _url(workspace.slug),
        headers=superuser_account_token_headers,
        json={
            "platform": "instagram",
            "instagram_business_account_id": "17840000000000000",
        },
    )
    assert instagram.status_code == 200
    assert instagram.json()["status"] == "connected"


def test_member_cannot_connect(client: TestClient, session: Session) -> None:
    _, workspace = _owned_workspace(session)
    _, headers = create_random_account_with_token(
        client,
        session,
        account_action,
        oauth_url=f"{settings.API_V1_STR}/login",
        email="member.platforms@example.com",
        password="s3cret-pass",
    )
    account = account_action.get_by_email(session, email="member.platforms@example.com")
    assert account is not None
    user_action.create_membership(
        session,
        account_id=account.id,
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        membership_type=UserType.member,
    )
    response = client.post(
        _url(workspace.slug),
        headers=headers,
        json={"platform": "whatsapp", "display_phone_number": "2348095550100"},
    )
    assert response.status_code == 403
