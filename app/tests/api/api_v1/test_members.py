from uuid import uuid4

from fastapi.testclient import TestClient
from msflib.utils.tests.account import create_random_account_with_token
from sqlmodel import Session

from app.actions import account_action, user_action, workspace_action
from app.core.config import settings
from app.models import UserType


def _owned_workspace(session: Session):
    account = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert account is not None
    rows = workspace_action.get_multi_by_all(session, owner_id=account.id, limit=5)
    assert rows
    return account, rows[0]


def _users_url(slug: str) -> str:
    return f"{settings.API_V1_STR}/{slug}/users"


def _body(**extra: object) -> dict[str, object]:
    suffix = uuid4().hex[:10]
    body: dict[str, object] = {
        "email": f"member{suffix}@example.com",
        "phone": f"+2348{suffix[:8]}",
        "password": "s3cret-pass",
        "first_name": "Ada",
        "last_name": "Chef",
        "type": "member",
    }
    body.update(extra)
    return body


def _grant(
    session: Session, *, email: str, workspace_id: int, owner_id: int, role: UserType
):
    account = account_action.get_by_email(session, email=email)
    assert account is not None
    membership = user_action.create_membership(
        session,
        account_id=account.id,
        workspace_id=workspace_id,
        owner_id=owner_id,
        membership_type=role,
        commit=False,
    )
    membership.type = role
    session.add(membership)
    session.commit()
    return account


def test_owner_creates_member_with_password_and_lists_them(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
    mocker,
) -> None:
    send_email = mocker.patch("msflib.services.email.send_new_account_email")
    _, workspace = _owned_workspace(session)
    body = _body()

    created = client.post(
        _users_url(workspace.slug),
        json=body,
        headers=superuser_account_token_headers,
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["email"] == body["email"]
    assert payload["phone"] == body["phone"]
    assert payload["type"] == "member"
    assert payload["first_name"] == "Ada"
    assert payload["last_name"] == "Chef"
    assert payload["display_name"] == "Ada Chef"
    assert payload["workspace_id"] == workspace.id
    assert "password" not in payload
    assert "hashed_password" not in payload
    send_email.assert_not_called()

    account = account_action.get_by_email(session, email=str(body["email"]))
    assert account is not None
    assert account.hashed_password
    assert account.hashed_password != body["password"]
    assert account.current_workspace_id == workspace.id
    assert (
        workspace_action.get_multi_by_all(session, owner_id=account.id, limit=5) == []
    )

    listed = client.get(
        _users_url(workspace.slug), headers=superuser_account_token_headers
    )
    assert listed.status_code == 200
    match = next(row for row in listed.json() if row["email"] == body["email"])
    assert match["type"] == "member"
    assert match["phone"] == body["phone"]

    logged_in = client.post(
        f"{settings.API_V1_STR}/login",
        data={"username": body["email"], "password": body["password"]},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["access_token"]


def test_create_member_rejects_owner_role_and_duplicates(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    owner_role = client.post(
        _users_url(workspace.slug),
        json=_body(type="owner"),
        headers=superuser_account_token_headers,
    )
    assert owner_role.status_code == 422

    body = _body(type="admin")
    first = client.post(
        _users_url(workspace.slug),
        json=body,
        headers=superuser_account_token_headers,
    )
    assert first.status_code == 201
    assert first.json()["type"] == "admin"

    duplicate = client.post(
        _users_url(workspace.slug),
        json=body,
        headers=superuser_account_token_headers,
    )
    assert duplicate.status_code == 422


def test_member_cannot_list_or_create_members(
    client: TestClient, session: Session
) -> None:
    _, workspace = _owned_workspace(session)
    _, headers = create_random_account_with_token(
        client,
        session,
        account_action,
        oauth_url=f"{settings.API_V1_STR}/login",
        email="member.team@example.com",
        password="s3cret-pass",
    )
    _grant(
        session,
        email="member.team@example.com",
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        role=UserType.member,
    )

    listed = client.get(_users_url(workspace.slug), headers=headers)
    created = client.post(_users_url(workspace.slug), json=_body(), headers=headers)
    assert listed.status_code == 403
    assert created.status_code == 403


def test_admin_can_add_a_guest(client: TestClient, session: Session) -> None:
    _, workspace = _owned_workspace(session)
    _, headers = create_random_account_with_token(
        client,
        session,
        account_action,
        oauth_url=f"{settings.API_V1_STR}/login",
        email="admin.team@example.com",
        password="s3cret-pass",
    )
    _grant(
        session,
        email="admin.team@example.com",
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        role=UserType.admin,
    )

    created = client.post(
        _users_url(workspace.slug),
        json=_body(type="guest"),
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["type"] == "guest"


def test_members_require_auth(client: TestClient, session: Session) -> None:
    _, workspace = _owned_workspace(session)
    listed = client.get(_users_url(workspace.slug))
    created = client.post(_users_url(workspace.slug), json=_body())
    assert listed.status_code in {401, 403}
    assert created.status_code in {401, 403}
