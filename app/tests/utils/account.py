from typing import Dict

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import actions
from app.core.config import settings
from app.models.account import (
    Account,
    AccountCreate,
    AccountRole,
    AccountStatus,
    AccountUpdate,
)
from app.tests.utils.utils import (
    random_email,
    random_lower_string,
    random_phone_number,
)


def account_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> Dict[str, str]:
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_account(session: Session, **data: dict) -> Account:
    data = random_account_create(**data)
    account = actions.account.create(session=session, data=data)
    return account


def create_random_account_with_token(client: TestClient, session: Session, **data: dict):
    if data.get("password") is None:
        password = random_lower_string()
        data["password"] = password
    else:
        password = data["password"]

    account = create_random_account(session, **data)
    r = client.post(
        f"{settings.API_V1_STR}/login",
        data={
            "username": account.email,
            "password": password,
        },
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return account, headers


def random_account_create(**data: dict) -> AccountCreate:
    return AccountCreate(
        username=data.get("username", random_email()),
        email=data.get("email", random_email()),
        password=data.get("password", random_lower_string()),
        phone=data.get("phone", random_phone_number()),
        status=data.get("status", AccountStatus.active),
        role=data.get("role", AccountRole.user),
    )


def authentication_token_from_email(
    *, client: TestClient, email: str, session: Session
) -> Dict[str, str]:
    """
    Return a valid token for the account with given email.

    If the account doesn't exist it is created first.
    """
    password = random_lower_string()
    account = actions.account.get_by_email(session, email=email)
    if not account:
        data = random_account_create(accountname=email, email=email, password=password)
        account = actions.account.create(session, data=data)
    else:
        data = AccountUpdate(password=password)
        account = actions.account.update(session, model=account, data=data)

    return account_authentication_headers(client=client, email=email, password=password)
