"""List ingested WhatsApp and Meta messages for the active workspace."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from msflib.models import SchemaBase
from sqlmodel import Session, select

from app import models
from app.api import deps
from app.ingestion.serializers import ingested_message_read
from app.models import IngestedMessage, MessageCategory

router = APIRouter()

_list_role = deps.WorkspaceRoleCheck([models.UserType.owner, models.UserType.admin])


class IngestedMessageRead(SchemaBase):
    id: int
    workspace_id: int
    channel_type: str
    provider_message_id: str
    sender: str | None = None
    customer_name: str | None = None
    display_phone_number: str | None = None
    category: str | None = None
    body: str
    parsed_metadata: dict | None = None
    timestamp: datetime
    created_at: datetime | None = None


@router.get(
    "/{workspace_slug}/ingested-messages",
    response_model=list[IngestedMessageRead],
    dependencies=[Depends(_list_role)],
)
def read_ingested_messages(
    category: Literal["enquiry", "order"] | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> list[dict]:
    statement = (
        select(IngestedMessage)
        .where(IngestedMessage.workspace_id == workspace.id)
        .order_by(IngestedMessage.timestamp.desc())
        .limit(limit)
    )
    if category is not None:
        statement = statement.where(
            IngestedMessage.category == MessageCategory(category)
        )
    rows = session.exec(statement).all()
    return [ingested_message_read(row) for row in rows]


@router.get(
    "/{workspace_slug}/ingested-messages/{message_id}",
    response_model=IngestedMessageRead,
    dependencies=[Depends(_list_role)],
)
def read_ingested_message(
    message_id: int,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> dict:
    row = session.get(IngestedMessage, message_id)
    if row is None or row.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Message not found")
    return ingested_message_read(row)
