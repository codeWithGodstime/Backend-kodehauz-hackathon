from datetime import datetime, timedelta
from typing import Dict

from fastapi.encoders import isoformat
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models import AccountRead, UserReadPublic
from app.tests.utils.account import create_random_account, random_email
from app.tests.utils.user import create_random_user
from app.tests.utils.workspace import create_random_workspace_and_account
from app.utils import generate_password_reset_token


def test_get_access_token(client: TestClient, session: Session) -> None:
    workspace, _ = create_random_workspace_and_account(session)
    user = create_random_user(session, workspace, password="password")
    login_data = {
        "username": user.account.email,
        "password": "password",
    }
    r = client.post(f"{settings.API_V1_STR}/login", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]
    expire = isoformat(datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    assert tokens["expires"].split(".")[0] == expire.split(".")[0]
    assert tokens["user"] == UserReadPublic.from_orm(user).jsond()
    assert tokens["account"] == AccountRead.from_orm(user.account).jsond()


def test_use_access_token(
    client: TestClient, superuser_account_token_headers: Dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/test-access-token",
        headers=superuser_account_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert "email" in result


def test_clear_access_token(
    client: TestClient, superuser_account_token_headers: Dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/test-access-token",
        headers=superuser_account_token_headers,
    )
    assert r.status_code == 200

    r1 = client.delete(
        f"{settings.API_V1_STR}/logout",
        headers=superuser_account_token_headers,
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"{settings.API_V1_STR}/test-access-token",
        headers=superuser_account_token_headers,
    )
    assert r2.status_code == 401

    r3 = client.post(
        f"{settings.API_V1_STR}/login",
        data={
            "username": settings.FIRST_SUPERUSER.upper(),
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert r3.status_code == 200
    token = r3.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r4 = client.post(
        f"{settings.API_V1_STR}/test-access-token",
        headers=headers,
    )
    assert r4.status_code == 200


def test_reset_password_links(
    client: TestClient,
    session: Session,
    mock_send_email,
) -> None:
    account = create_random_account(session)
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery",
        json={"email": account.email},
    )
    assert r.status_code == 200
    password_reset_token = generate_password_reset_token(email=account.email)
    r1 = client.post(
        f"{settings.API_V1_STR}/reset-password",
        json={"token": password_reset_token, "new_password": "welcome"},
    )
    assert r1.status_code == 200
    session.refresh(account)
    assert verify_password("welcome", account.hashed_password)


def test_reset_password_links_nonexistent(client: TestClient, session: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery",
        json={"email": random_email()},
    )
    assert r.status_code == 404


def test_reset_password_invalid_token(client: TestClient, session: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/reset-password",
        json={
            "token": generate_password_reset_token(email=random_email()),
            "new_password": "welcome",
        },
    )
    assert r.status_code == 404
