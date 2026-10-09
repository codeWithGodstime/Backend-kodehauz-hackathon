"""Demo seed attaches the dev user, members, and one WhatsApp business line."""

from sqlmodel import Session, func, select

from app.actions import account_action
from app.core.config import settings
from app.models import PlatformConnection, User, Workspace
from app.seed.demo import (
    BUSINESS_DISPLAY_PHONE_NUMBER,
    DEV_USER_PHONE,
    MEMBERS,
    ensure_socialchef_seed,
)


def test_ensure_socialchef_seed_is_idempotent(session: Session) -> None:
    ensure_socialchef_seed(session)
    ensure_socialchef_seed(session)

    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert owner is not None
    assert owner.phone == DEV_USER_PHONE
    assert owner.current_workspace_id is not None

    workspace = session.get(Workspace, owner.current_workspace_id)
    assert workspace is not None
    memberships = session.exec(select(User).where(User.workspace_id == workspace.id)).all()
    phones = set()
    for membership in memberships:
        account = account_action.get(session, id=membership.account_id)
        assert account is not None
        phones.add(account.phone)
    assert DEV_USER_PHONE in phones
    for spec in MEMBERS:
        assert spec["phone"] in phones

    connections = session.exec(
        select(func.count()).select_from(PlatformConnection).where(
            PlatformConnection.workspace_id == workspace.id
        )
    ).one()
    assert connections == 1
    row = session.exec(
        select(PlatformConnection).where(PlatformConnection.workspace_id == workspace.id)
    ).one()
    assert row.display_phone_number == BUSINESS_DISPLAY_PHONE_NUMBER
    assert str(row.status) == "connected"
    assert row.access_token is None
