"""Workspace catalog routes the React workspace client calls directly.

``GET /workspaces`` is the owned-workspace list. ``GET /workspaces/available``
is the cross-workspace list used when available calls are not path-scoped.
Both paths are registered without a trailing slash so they match the client
URLs instead of redirecting.
"""

from typing import Any

from fastapi import APIRouter, Depends
from msflib.models import SchemaBase
from msflib.workspaces.models import UserStatus, WorkspaceStatus
from sqlalchemy import or_
from sqlmodel import Session

from app import models
from app.actions import user_action, workspace_action
from app.api import deps

router = APIRouter()


class WorkspaceListItem(SchemaBase):
    id: int
    created_at: str | None = None
    updated_at: str | None = None
    name: str
    label: str
    slug: str
    description: str
    status: str
    logo: str
    logo_url: str | None = None
    owner_id: int
    is_default: bool = False
    registration_link: str
    publish_to_users: bool
    start_date: str
    end_date: str
    settings: dict[str, Any] | None = None
    data: dict[str, Any] | None = None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _workspace_item(workspace: Any) -> WorkspaceListItem:
    settings = workspace.settings if isinstance(workspace.settings, dict) else {}
    logo_url = workspace.logo_url
    created_at = getattr(workspace, "created_at", None)
    updated_at = getattr(workspace, "updated_at", None)
    return WorkspaceListItem(
        id=workspace.id,
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
        name=workspace.name,
        label=workspace.name,
        slug=workspace.slug,
        description=workspace.description or "",
        status=_text(workspace.status),
        logo=logo_url or "",
        logo_url=logo_url,
        owner_id=workspace.owner_id,
        is_default=bool(workspace.is_default),
        registration_link=_text(settings.get("registration_link")),
        publish_to_users=bool(settings.get("publish_to_users")),
        start_date=_text(settings.get("start_date")),
        end_date=_text(settings.get("end_date")),
        settings=settings or None,
        data=workspace.data if isinstance(workspace.data, dict) else None,
    )


@router.get("/workspaces", response_model=list[WorkspaceListItem])
def list_workspaces(
    session: Session = Depends(deps.get_session),
    offset: int = 0,
    limit: int = 100,
    account: models.Account = Depends(deps.get_current_account),
) -> list[WorkspaceListItem]:
    rows = workspace_action.get_multi_by_all(
        session=session,
        offset=offset,
        limit=limit,
        owner_id=account.id,
    )
    return [_workspace_item(row) for row in rows]


@router.get("/workspaces/available", response_model=list[WorkspaceListItem])
def list_available_workspaces(
    session: Session = Depends(deps.get_session),
    offset: int = 0,
    limit: int = 100,
    account: models.Account = Depends(deps.get_current_account),
) -> list[WorkspaceListItem]:
    memberships = user_action.get_multi_by_all(
        session,
        account_id=account.id,
        offset=offset,
        limit=limit,
    )
    member_ids = [
        membership.workspace_id
        for membership in memberships
        if membership.status != UserStatus.banned
        and membership.workspace.status != WorkspaceStatus.locked
    ]
    filters = [
        models.Workspace.status == WorkspaceStatus.open,
        models.Workspace.owner_id == account.id,
    ]
    if member_ids:
        filters.append(models.Workspace.id.in_(member_ids))  # type: ignore[attr-defined]
    rows = workspace_action.get_multi_by_expressions(
        session,
        or_(*filters),
        offset=offset,
        limit=limit,
    )
    return [_workspace_item(row) for row in rows]
