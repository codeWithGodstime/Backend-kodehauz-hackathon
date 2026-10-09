"""Admin connect / disconnect for WhatsApp, Facebook, and Instagram.

Owner and admin workspace memberships can change a connection. The action
writes a row the admin marked connected or disconnected. It does not perform
an OAuth redirect and does not store a token that pretends to come from Meta.

Real Meta credentials, when a production app is configured:

- ``META_APP_ID`` — Meta app id (not read by this service today).
- ``META_APP_SECRET`` — already used to verify webhook signatures.
- ``META_WEBHOOK_VERIFY_TOKEN`` — already used for the hub challenge.
- WhatsApp — Cloud API ``phone_number_id``, the business
  ``display_phone_number``, and a system-user token with
  ``whatsapp_business_messaging``. That token would be stored in
  ``platform_connection.access_token`` by a future OAuth callback.
- Facebook — Page id (``page_id``) and a Page access token.
- Instagram — ``instagram_business_account`` id for the professional account
  linked to that Facebook Page, plus the Page access token.

``access_token`` is never returned and never logged.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from msflib.models import SchemaBase
from sqlmodel import Session

from app import models
from app.api import deps
from app.platforms.connection import (
    PlatformConnectionError,
    connect_platform,
    connection_read,
    disconnect_platform,
    get_connection,
    list_connections,
)

router = APIRouter()

_manage_role = deps.WorkspaceRoleCheck([models.UserType.owner, models.UserType.admin])


class PlatformConnectionRead(SchemaBase):
    id: int
    workspace_id: int
    platform: str
    status: str
    display_phone_number: str | None = None
    phone_number_id: str | None = None
    page_id: str | None = None
    instagram_business_account_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlatformConnectionConnect(SchemaBase):
    platform: str
    display_phone_number: str | None = None
    phone_number_id: str | None = None
    page_id: str | None = None
    instagram_business_account_id: str | None = None


@router.get(
    "/{workspace_slug}/platform-connections",
    response_model=list[PlatformConnectionRead],
    dependencies=[Depends(_manage_role)],
)
def read_platform_connections(
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> list[dict]:
    return [
        connection_read(row)
        for row in list_connections(session, workspace_id=workspace.id)
    ]


@router.get(
    "/{workspace_slug}/platform-connections/{connection_id}",
    response_model=PlatformConnectionRead,
    dependencies=[Depends(_manage_role)],
)
def read_platform_connection(
    connection_id: int,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> dict:
    row = get_connection(session, workspace_id=workspace.id, connection_id=connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Platform connection not found")
    return connection_read(row)


@router.post(
    "/{workspace_slug}/platform-connections",
    response_model=PlatformConnectionRead,
    dependencies=[Depends(_manage_role)],
)
def connect_workspace_platform(
    body: PlatformConnectionConnect,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> dict:
    try:
        row = connect_platform(
            session,
            workspace_id=workspace.id,
            platform=body.platform,
            display_phone_number=body.display_phone_number,
            phone_number_id=body.phone_number_id,
            page_id=body.page_id,
            instagram_business_account_id=body.instagram_business_account_id,
        )
    except PlatformConnectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return connection_read(row)


@router.post(
    "/{workspace_slug}/platform-connections/{connection_id}/disconnect",
    response_model=PlatformConnectionRead,
    dependencies=[Depends(_manage_role)],
)
def disconnect_workspace_platform(
    connection_id: int,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> dict:
    row = disconnect_platform(
        session, workspace_id=workspace.id, connection_id=connection_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Platform connection not found")
    return connection_read(row)
