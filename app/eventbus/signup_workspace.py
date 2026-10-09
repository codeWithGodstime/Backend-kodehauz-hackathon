"""Create the signing-up account's own workspace.

Open registration emits ``account-created`` after the account row is committed.
The workspaces module may already have added that account to the tenant's
shared default workspace on ``account-create-pre-commit``. That default is not
this account's workspace unless they own it. This listener creates one
workspace they own, and does not insert a second one when they already do.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from msflib.account.actions import AccountAction
from msflib.account.eventbus import EventName as AccountEventName
from msflib.account.models import AccountCreate, AccountUpdate
from msflib.eventbus import AppEmitter
from msflib.tenancy.models.tenant import Tenant
from msflib.tenancy.resolver import resolve_default_tenant_id
from msflib.utils.utils import slugify
from msflib.workspaces.models import UserType, WorkspaceCreate, WorkspaceStatus
from msflib.workspaces.router import get_forbidden_ws_names
from sqlmodel import Session

from app.actions import profile_action, user_action, workspace_action
from app.billing.subscriptions import UnknownPlan, signup_plan_selection
from app.core.config import settings
from app.models import Account

logger = logging.getLogger(__name__)

_forbidden_slugs: set[str] | None = None


class SignupAccountCreate(AccountCreate):
    """Open-registration body.

    ``workspace_name`` is optional. ``plan_key`` selects a catalog plan.
    ``skip_plan`` finishes signup without a plan.
    """

    workspace_name: str | None = None
    plan_key: str | None = None
    skip_plan: bool = False


class SignupAccountAction(AccountAction[Account, SignupAccountCreate, AccountUpdate]):
    """Account create used by open registration.

    Keeps the library ``/open`` handler and records the plan choice on
    ``account.data['onboarding']`` before the library insert.
    """

    def create(
        self,
        session: Session,
        *,
        data: SignupAccountCreate,
        update: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Account:
        try:
            selection = signup_plan_selection(session, data)
        except UnknownPlan as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        current = data.data if isinstance(data.data, dict) else {}
        data.data = {**current, "onboarding": selection}
        return super().create(session, data=data, update=update, commit=commit)


signup_account_action = SignupAccountAction(
    settings=settings,
    profile_action=profile_action,
)


def register_signup_workspace(emitter: AppEmitter) -> None:
    @emitter.listen(AccountEventName.ACCOUNT_CREATED)
    def _on_account_created(account: Any, options: dict[str, Any], logger: Any = None) -> None:
        create_signup_workspace(account, options, logger=logger)


def create_signup_workspace(account: Any, options: dict[str, Any], logger: Any = None) -> Any:
    """Create a workspace owned by ``account`` and an owner membership row.

    Returns the workspace the account owns. When one already exists (including
    the module default workspace, if this account is its owner), that row is
    reused and no second workspace is inserted.

    The ``workspace_user`` row is inserted by ``UserAction.create_membership``.
    ``WorkspaceAction.create_with_owner`` also emits ``workspace-create-pre-commit``,
    whose hook calls the same method first; the call here is idempotent and
    still inserts the row when that hook is not active. The role is
    ``UserType.owner``.
    """
    log = logger or logging.getLogger(__name__)
    session: Session | None = options.get("session")
    if session is None or getattr(account, "id", None) is None:
        log.error("account-created is missing a session or account id; workspace was not created")
        return None

    owned = workspace_action.get_by_all(session, owner_id=account.id)
    if owned is not None:
        _ensure_owner_membership(session, account_id=account.id, workspace=owned)
        _point_account_at_workspace(session, account, owned.id)
        session.commit()
        session.refresh(account)
        return owned

    tenant_id = resolve_default_tenant_id(session, settings=settings.scope("TENANCY"))
    tenant = session.get(Tenant, tenant_id) if tenant_id is not None else None
    if tenant is None:
        raise RuntimeError("Default tenant has not been seeded")

    name = _acceptable_workspace_name(
        workspace_name_from_signup(account, options.get("data")),
        account_id=account.id,
    )
    workspace = workspace_action.create_with_owner(
        session,
        data=WorkspaceCreate(
            name=name,
            description=name,
            owner_id=account.id,
            status=WorkspaceStatus.open,
            is_default=False,
        ),
        owner=account,
        tenant=tenant,
        commit=False,
    )
    _ensure_owner_membership(session, account_id=account.id, workspace=workspace)
    _point_account_at_workspace(session, account, workspace.id)
    session.commit()
    session.refresh(account)
    return workspace


def workspace_name_from_signup(account: Any, data: Any | None) -> str:
    """Name from an optional signup field, then the account, then the email."""
    explicit = _text(_value(data, "workspace_name"))
    if explicit:
        return explicit

    profile = _value(data, "profile")
    if profile is None:
        profile = getattr(account, "profile", None)
    parts = [
        part
        for part in (
            _text(_value(profile, "first_name")),
            _text(_value(profile, "last_name")),
        )
        if part
    ]
    if parts:
        return " ".join(parts)

    username = _text(getattr(account, "username", None))
    if username:
        return username

    email = _text(getattr(account, "email", None)) or ""
    local = email.split("@", 1)[0].strip()
    return local or "Workspace"


def _ensure_owner_membership(session: Session, *, account_id: int, workspace: Any) -> None:
    user_action.create_membership(
        session,
        account_id=account_id,
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        membership_type=UserType.owner,
        commit=False,
    )


def _point_account_at_workspace(session: Session, account: Any, workspace_id: int) -> None:
    if getattr(account, "current_workspace_id", None) != workspace_id:
        account.current_workspace_id = workspace_id
        session.add(account)


def _acceptable_workspace_name(name: str, *, account_id: int) -> str:
    forbidden = _forbidden_workspace_slugs()
    candidate = name.strip() or "Workspace"
    if _slug_allowed(candidate, forbidden):
        return candidate
    fallback = f"{candidate} {account_id}".strip()
    if _slug_allowed(fallback, forbidden):
        return fallback
    return f"workspace {account_id}"


def _slug_allowed(name: str, forbidden: set[str]) -> bool:
    slug = slugify(name)
    return bool(slug) and slug not in forbidden


def _forbidden_workspace_slugs() -> set[str]:
    global _forbidden_slugs
    if _forbidden_slugs is None:
        _forbidden_slugs = set(get_forbidden_ws_names())
    return _forbidden_slugs


def _value(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
