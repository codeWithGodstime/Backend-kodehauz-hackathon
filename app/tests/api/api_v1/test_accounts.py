from typing import Dict

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models.account import AccountRole, AccountStatus, AccountUpdate
from app.tests.utils.account import create_random_account_with_token
from app.tests.utils.utils import random_email


def test_get_accounts_superuser_me(
    client: TestClient, superuser_account_token_headers: Dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/me", headers=superuser_account_token_headers)
    account = r.json()
    assert account
    assert account["status"] == AccountStatus.active.value
    assert account["role"] == AccountRole.admin.value
    assert account["email"] == settings.FIRST_SUPERUSER


def test_get_accounts_normal_me(
    client: TestClient, normal_account_token_headers: Dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/me", headers=normal_account_token_headers)
    account = r.json()
    assert account
    assert account["status"] == AccountStatus.active.value
    assert account["role"] == AccountRole.user.value
    assert account["email"] == settings.EMAIL_TEST_ACCOUNT


def test_change_password(client: TestClient, session: Session) -> None:
    account, headers = create_random_account_with_token(client, session)
    uuu = {
        "id": account.id,
        "email": account.email,
        "hashed_password": account.hashed_password,
    }

    data = AccountUpdate(password="new password", email=random_email())
    response = client.put(f"{settings.API_V1_STR}/me", headers=headers, json=data.jsond())
    assert response.status_code == 200

    # Refresh session to get updated values.
    session.refresh(account)
    assert account.id == uuu["id"]
    assert account.email != uuu["email"]
    assert account.hashed_password != uuu["hashed_password"]
    assert verify_password(data.password, account.hashed_password)


@pytest.mark.skip(reason="Endpoint removed during refactor.")
def test_get_existing_account_self(client: TestClient, session: Session) -> None:
    account, headers = create_random_account_with_token(client, session)
    r = client.get(
        f"{settings.API_V1_STR}/account/{account.id}",
        headers=headers,
    )
    assert r.status_code == 200
    api_user = r.json()
    assert account.email == api_user["email"]
