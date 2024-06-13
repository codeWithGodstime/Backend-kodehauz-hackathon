from typing import Dict

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import actions
from app.core.config import settings
from app.models.account import AccountRead, AccountUpdate
from app.tests.utils.account import (
    create_random_account,
    create_random_account_with_token,
    random_account_create,
)
from app.tests.utils.utils import random_email


def test_get_existing_account(
    client: TestClient, superuser_account_token_headers: dict, session: Session
) -> None:
    account = create_random_account(session)
    r = client.get(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=superuser_account_token_headers,
    )
    assert r.status_code == 200
    api_account = r.json()
    assert api_account == AccountRead.from_orm(account).jsond()


def test_get_existing_account_unauthorized(client: TestClient, session: Session) -> None:
    account, headers = create_random_account_with_token(client, session)
    r = client.get(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=headers,
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authorized"


def test_create_account_new_email(
    client: TestClient, superuser_account_token_headers: dict, session: Session
) -> None:
    data = random_account_create()
    r = client.post(
        f"{settings.API_V1_STR}/admin/accounts",
        headers=superuser_account_token_headers,
        json=data.jsond(),
    )
    assert r.status_code == 201
    created_account = r.json()
    account = actions.account.get_by_email(session, email=data.email)
    assert account
    assert account.email == created_account["email"]


def test_create_account_existing_username(
    client: TestClient, superuser_account_token_headers: dict, session: Session
) -> None:
    account = create_random_account(session)
    data = random_account_create(username=account.username)
    r = client.post(
        f"{settings.API_V1_STR}/admin/accounts",
        headers=superuser_account_token_headers,
        json=data.jsond(),
    )
    created_account = r.json()
    assert r.status_code == 422
    assert "_id" not in created_account


def test_create_account_existing_email(
    client: TestClient, superuser_account_token_headers: dict, session: Session
) -> None:
    account = create_random_account(session)
    data = random_account_create(email=account.email)
    r = client.post(
        f"{settings.API_V1_STR}/admin/accounts",
        headers=superuser_account_token_headers,
        json=data.jsond(),
    )
    created_account = r.json()
    assert r.status_code == 422
    assert "_id" not in created_account


def test_create_account_existing_phone(
    client: TestClient, superuser_account_token_headers: dict, session: Session
) -> None:
    account = create_random_account(session)
    data = random_account_create(phone=account.phone)
    r = client.post(
        f"{settings.API_V1_STR}/admin/accounts",
        headers=superuser_account_token_headers,
        json=data.jsond(),
    )
    created_account = r.json()
    assert r.status_code == 422
    assert "_id" not in created_account


def test_create_account_by_normal_account(
    client: TestClient, normal_account_token_headers: Dict[str, str]
) -> None:
    data = random_account_create()
    r = client.post(
        f"{settings.API_V1_STR}/admin/accounts",
        headers=normal_account_token_headers,
        json=data.jsond(),
    )
    assert r.status_code == 401


def test_retrieve_accounts(
    client: TestClient, superuser_account_token_headers: dict, session: Session
) -> None:
    accounts = [create_random_account(session) for count in range(2)]

    r = client.get(
        f"{settings.API_V1_STR}/admin/accounts",
        params={"limit": 500},
        headers=superuser_account_token_headers,
    )
    all_accounts = r.json()

    assert len(all_accounts) > 1
    emails = []
    for item in all_accounts:
        assert "email" in item
        emails.append(item["email"])

    for account in accounts:
        assert account.email in emails


def test_account_get_unauthorized(
    client: TestClient,
    session: Session,
    normal_account_token_headers: dict,
) -> None:
    account = create_random_account(session)
    response = client.get(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=normal_account_token_headers,
    )
    assert response.status_code == 401
    content = response.json()
    assert content["detail"] == "Not authorized"


def test_account_put(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict,
) -> None:
    account = create_random_account(session)
    data = AccountUpdate(email=random_email())
    response = client.put(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=superuser_account_token_headers,
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
    account = create_random_account(session)
    AccountUpdate(email=random_email())
    response = client.put(
        f"{settings.API_V1_STR}/admin/accounts/{account.id}",
        headers=normal_account_token_headers,
    )
    assert response.status_code == 401


def test_account_put_non_existent(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict,
) -> None:
    data = AccountUpdate(email=random_email())
    response = client.put(
        f"{settings.API_V1_STR}/admin/accounts/100000",
        headers=superuser_account_token_headers,
        json=data.jsond(),
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "The account with this id does not exist in the system."
