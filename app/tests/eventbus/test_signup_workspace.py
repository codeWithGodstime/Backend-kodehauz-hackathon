from msflib.account.models import ProfileCreate
from msflib.eventbus import emitter, use_app_emitter
from msflib.workspaces.models import UserType
from sqlmodel import Session

from app.actions import account_action, user_action, workspace_action
from app.core.config import settings
from app.eventbus.signup_workspace import (
    SignupAccountCreate,
    create_signup_workspace,
    workspace_name_from_signup,
)
from app.main import app
from app.models import AccountCreate


def test_workspace_name_uses_profile_then_email_local_part() -> None:
    named = SignupAccountCreate(
        email="ada@example.com",
        password="s3cret-pass",
        profile=ProfileCreate(first_name="Ada", last_name="Lovelace"),
    )
    assert workspace_name_from_signup(named, named) == "Ada Lovelace"

    email_only = AccountCreate(email="chef.ada@example.com", password="s3cret-pass")
    assert workspace_name_from_signup(email_only, email_only) == "chef.ada"

    custom = SignupAccountCreate(
        email="ada@example.com",
        password="s3cret-pass",
        workspace_name="Ada's Kitchen",
    )
    assert workspace_name_from_signup(custom, custom) == "Ada's Kitchen"


def test_account_created_creates_owned_workspace(session: Session) -> None:
    data = SignupAccountCreate(
        email="ada.signup@example.com",
        password="s3cret-pass",
        profile=ProfileCreate(first_name="Ada", last_name="Lovelace"),
    )
    with use_app_emitter(app):
        account = account_action.create(session, data=data)
        emitter.emit_optional(
            "account-created",
            account,
            {"session": session, "data": data},
        )

    session.refresh(account)
    owned = workspace_action.get_multi_by_all(session, owner_id=account.id, limit=10)
    assert len(owned) == 1
    workspace = owned[0]
    assert workspace.name == "Ada Lovelace"
    assert workspace.is_default is False
    assert workspace.tenant_id is not None
    assert account.current_workspace_id == workspace.id

    membership = user_action.get_by_all(
        session, account_id=account.id, workspace_id=workspace.id
    )
    assert membership is not None
    assert membership.type == UserType.owner

    with use_app_emitter(app):
        again = create_signup_workspace(account, {"session": session, "data": data})
    assert again.id == workspace.id
    assert len(workspace_action.get_multi_by_all(session, owner_id=account.id, limit=10)) == 1


def test_signup_does_not_create_a_second_workspace_for_an_existing_owner(
    session: Session,
) -> None:
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert owner is not None
    before = workspace_action.get_multi_by_all(session, owner_id=owner.id, limit=10)
    assert before

    with use_app_emitter(app):
        create_signup_workspace(owner, {"session": session, "data": None})

    after = workspace_action.get_multi_by_all(session, owner_id=owner.id, limit=10)
    assert [row.id for row in after] == [row.id for row in before]
    session.refresh(owner)
    assert owner.current_workspace_id == before[0].id
