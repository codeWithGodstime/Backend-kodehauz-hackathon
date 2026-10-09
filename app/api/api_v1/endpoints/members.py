"""Workspace member list and direct create for owner and admin memberships.

Account creation uses ``AccountAction.create``, which hashes the supplied
password. It does not call the account service that emails the password, and
it does not emit ``account-created``, so signup does not open a second
workspace for the new account.
"""

from fastapi import APIRouter, Depends, HTTPException
from msflib.models import SchemaBase
from msflib.workspaces.models import UserStatus
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import models
from app.actions import account_action, profile_action, user_action
from app.api import deps

router = APIRouter()

_ASSIGNABLE_ROLES = (
    models.UserType.admin,
    models.UserType.member,
    models.UserType.guest,
)
_manage_members = deps.WorkspaceRoleCheck(
    [models.UserType.owner, models.UserType.admin]
)


class WorkspaceMemberCreate(SchemaBase):
    email: EmailStr
    phone: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    type: models.UserType = models.UserType.member


class WorkspaceMemberRead(SchemaBase):
    id: int
    account_id: int
    workspace_id: int
    type: models.UserType
    status: UserStatus
    display_name: str | None = None
    email: str
    phone: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _role(value: models.UserType | str) -> models.UserType:
    return value if isinstance(value, models.UserType) else models.UserType(value)


def _member_read(
    membership: models.User,
    account: models.Account,
    profile: models.Profile | None,
) -> WorkspaceMemberRead:
    if membership.id is None or account.id is None:
        raise HTTPException(status_code=500, detail="Member could not be read")
    return WorkspaceMemberRead(
        id=membership.id,
        account_id=membership.account_id,
        workspace_id=membership.workspace_id,
        type=membership.type,
        status=membership.status,
        display_name=membership.display_name,
        email=account.email,
        phone=account.phone,
        username=account.username,
        first_name=profile.first_name if profile is not None else None,
        last_name=profile.last_name if profile is not None else None,
    )


def _load_accounts(
    session: Session, account_ids: list[int]
) -> tuple[dict[int, models.Account], dict[int, models.Profile]]:
    if not account_ids:
        return {}, {}
    accounts = session.exec(
        select(models.Account).where(models.Account.id.in_(account_ids))  # type: ignore[attr-defined]
    ).all()
    profiles = session.exec(
        select(models.Profile).where(models.Profile.id.in_(account_ids))  # type: ignore[attr-defined]
    ).all()
    return (
        {account.id: account for account in accounts if account.id is not None},
        {profile.id: profile for profile in profiles if profile.id is not None},
    )


@router.get(
    "/{workspace_slug}/users",
    response_model=list[WorkspaceMemberRead],
    dependencies=[Depends(_manage_members)],
)
def list_workspace_members(
    offset: int = 0,
    limit: int = 100,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> list[WorkspaceMemberRead]:
    memberships = user_action.get_multi_by_all(
        session,
        workspace_id=workspace.id,
        offset=offset,
        limit=limit,
    )
    accounts, profiles = _load_accounts(
        session, [membership.account_id for membership in memberships]
    )
    rows: list[WorkspaceMemberRead] = []
    for membership in memberships:
        account = accounts.get(membership.account_id)
        if account is None:
            continue
        rows.append(
            _member_read(membership, account, profiles.get(membership.account_id))
        )
    return rows


@router.post(
    "/{workspace_slug}/users",
    response_model=WorkspaceMemberRead,
    status_code=201,
    dependencies=[Depends(_manage_members)],
)
def create_workspace_member(
    data: WorkspaceMemberCreate,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> WorkspaceMemberRead:
    role = _role(data.type)
    if role not in _ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail="Role must be one of: admin, member, guest.",
        )

    phone = _clean(data.phone)
    password = data.password.strip()
    if not phone:
        raise HTTPException(status_code=422, detail="Phone number is required")
    if not password:
        raise HTTPException(status_code=422, detail="Password is required")

    first_name = _clean(data.first_name)
    last_name = _clean(data.last_name)
    account_data = models.AccountCreate(
        email=data.email,
        phone=phone,
        password=password,
        status=models.AccountStatus.active,
        role=models.AccountRole.user,
    )
    account_action.ensure_unique_fields(session=session, data=account_data)
    account = account_action.create(session, data=account_data, commit=False)
    if account.id is None:
        raise HTTPException(status_code=500, detail="Account could not be created")

    if first_name or last_name:
        profile_action.create(
            session,
            data=models.ProfileCreate(first_name=first_name, last_name=last_name),
            update={"id": account.id},
            commit=False,
        )

    membership = user_action.create_membership(
        session,
        account_id=account.id,
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        membership_type=role,
        commit=False,
    )
    membership.type = role
    display_name = " ".join(part for part in (first_name, last_name) if part)
    if display_name:
        membership.display_name = display_name
    account.current_workspace_id = workspace.id
    session.add(membership)
    session.add(account)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail="An account with this email or phone already exists in the system",
        ) from exc

    session.refresh(membership)
    session.refresh(account)
    profile = profile_action.get(session, id=account.id)
    return _member_read(membership, account, profile)
