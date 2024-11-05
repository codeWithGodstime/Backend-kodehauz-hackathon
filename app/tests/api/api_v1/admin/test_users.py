from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import account as aa
from app.core.config import settings
from app.models.account import AccountRole, AccountUpdate
from app.tests.utils.account import (
    create_random_account_with_token,
)
from app.tests.utils.utils import random_email


def test_create_account_new_email(client: TestClient, session: Session) -> None:
    _, headers = create_random_account_with_token(client, session, role=AccountRole.admin)
    data = aa.random()
    r = client.post(
        f"{settings.API_V1_STR}/admin/accounts",
        headers=headers,
        json=data.jsond(),
    )
    assert r.status_code == 201
    created_user = r.json()
    account = aa.get_by_email(session, email=data.email)
    assert account
    assert account.email == created_user["email"]


def test_get_existing_account(client: TestClient, session: Session) -> None:
    _, headers = create_random_account_with_token(client, session, role=AccountRole.admin)
    account = aa.create_random(session)
    r = client.get(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=headers,
    )
    assert r.status_code == 200
    api_user = r.json()
    existing = aa.get_by_email(session, email=account.email)
    assert existing
    assert existing.email == api_user["email"]


def test_user_get_unauthorized(
    client: TestClient,
    session: Session,
    normal_account_token_headers: dict,
) -> None:
    account = aa.create_random(session)
    response = client.get(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=normal_account_token_headers,
    )
    assert response.status_code == 401
    content = response.json()
    assert content["detail"] == "Not authorized"


def test_retrieve_accounts(client: TestClient, session: Session) -> None:
    _, headers = create_random_account_with_token(client, session, role=AccountRole.admin)
    accounts = [aa.create_random(session) for count in range(2)]

    r = client.get(
        f"{settings.API_V1_STR}/admin/accounts",
        params={"limit": 500},
        headers=headers,
    )
    all_users = r.json()

    assert len(all_users) > 1
    emails = []
    for item in all_users:
        assert "email" in item
        emails.append(item["email"])

    for account in accounts:
        assert account.email in emails


def test_account_put(
    client: TestClient,
    session: Session,
) -> None:
    _, headers = create_random_account_with_token(client, session, role=AccountRole.admin)
    account = aa.create_random(session)
    data = AccountUpdate(email=random_email())
    response = client.put(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=headers,
        json=data.jsond(),
    )
    assert response.status_code == 200
    session.refresh(account)
    assert account.email == data.email


def test_account_put_unauthorized(
    client: TestClient,
    session: Session,
    normal_account_token_headers: dict,
) -> None:
    _, headers = create_random_account_with_token(client, session)
    account = aa.create_random(session)
    AccountUpdate(email=random_email())
    response = client.put(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=headers,
    )
    assert response.status_code == 401


def test_account_put_non_existent(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict,
) -> None:
    _, headers = create_random_account_with_token(client, session, role=AccountRole.admin)
    data = AccountUpdate(email=random_email())
    response = client.put(
        f"{settings.API_V1_STR}/admin/accounts/100000",
        headers=headers,
        json=data.jsond(),
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "The account with this id does not exist in the system."
