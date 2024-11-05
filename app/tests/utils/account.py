from typing import Dict

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import account as aa
from app.core.config import settings
from app.models.account import AccountUpdate

from app.tests.utils.utils import random_lower_string


def account_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> Dict[str, str]:
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_account_with_token(client: TestClient, session: Session, **data: dict):
    if data.get("password") is None:
        password = random_lower_string()
        data["password"] = password
    else:
        password = data["password"]

    account = aa.create_random(session, **data)
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


def authentication_token_from_email(
    *, client: TestClient, email: str, session: Session
) -> Dict[str, str]:
    """
    Return a valid token for the account with given email.

    If the account doesn't exist it is created first.
    """
    password = random_lower_string()
    account = aa.get_by_email(session, email=email)
    if not account:
        account = aa.create_random(session, accountname=email, email=email, password=password)
    else:
        account = aa.update(session, model=account, data=AccountUpdate(password=password))

    return account_authentication_headers(client=client, email=email, password=password)
