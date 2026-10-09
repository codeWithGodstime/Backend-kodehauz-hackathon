from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import account_action, workspace_action
from app.core.config import settings
from app.models import IngestedMessage, MessageCategory, UserType, Workspace


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _owned_workspace(session: Session) -> tuple[object, Workspace]:
    account = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert account is not None
    rows = workspace_action.get_multi_by_all(session, owner_id=account.id, limit=5)
    assert rows
    return account, rows[0]


def _add_message(
    session: Session,
    *,
    workspace_id: int,
    provider_message_id: str,
    category: MessageCategory,
    body: str,
) -> None:
    now = _utcnow()
    session.add(
        IngestedMessage(
            workspace_id=workspace_id,
            channel_type="whatsapp",
            provider_message_id=provider_message_id,
            sender="2348091001001",
            raw_payload=f'{{"type":"text","text":{{"body":"{body}"}}}}',
            category=category,
            parsed_metadata={"topic": "hours", "question_summary": body}
            if category == MessageCategory.enquiry
            else {"items": [{"name": "jollof rice", "quantity": 2}]},
            timestamp=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()


def test_list_ingested_messages_filters_by_category(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="wamid.test.enquiry",
        category=MessageCategory.enquiry,
        body="What time do you close?",
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="wamid.test.order",
        category=MessageCategory.order,
        body="2 plates of jollof",
    )
    base = f"{settings.API_V1_STR}/{workspace.slug}/ingested-messages"
    enquiry = client.get(
        f"{base}?category=enquiry",
        headers=superuser_account_token_headers,
    )
    assert enquiry.status_code == 200
    enquiry_rows = enquiry.json()
    assert len(enquiry_rows) >= 1
    assert all(row["category"] == "enquiry" for row in enquiry_rows)
    assert any(row["body"] == "What time do you close?" for row in enquiry_rows)

    orders = client.get(
        f"{base}?category=order",
        headers=superuser_account_token_headers,
    )
    assert orders.status_code == 200
    order_rows = orders.json()
    assert all(row["category"] == "order" for row in order_rows)
    assert any(row["body"] == "2 plates of jollof" for row in order_rows)


def test_member_cannot_list_ingested_messages(
    client: TestClient,
    session: Session,
    normal_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    url = f"{settings.API_V1_STR}/{workspace.slug}/ingested-messages"
    response = client.get(url, headers=normal_account_token_headers)
    assert response.status_code == 403
