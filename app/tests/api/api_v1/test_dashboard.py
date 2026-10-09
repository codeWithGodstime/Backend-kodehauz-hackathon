from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from msflib.utils.tests.account import create_random_account_with_token
from msflib.workspaces.models import WorkspaceStatus
from sqlmodel import Session

from app.actions import account_action, user_action, workspace_action
from app.core.config import settings
from app.models import Customer, IngestedMessage, MessageCategory, UserType, Workspace


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _owned_workspace(session: Session) -> tuple[object, Workspace]:
    account = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert account is not None
    rows = workspace_action.get_multi_by_all(session, owner_id=account.id, limit=5)
    assert rows
    return account, rows[0]


def _metrics_url(slug: str, query: str = "period=7d") -> str:
    return f"{settings.API_V1_STR}/{slug}/dashboard/metrics?{query}"


def _add_customer(
    session: Session,
    *,
    workspace_id: int,
    name: str,
    phone: str,
    created_at: datetime,
) -> Customer:
    customer = Customer(
        workspace_id=workspace_id,
        name=name,
        phone=phone,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


def _add_message(
    session: Session,
    *,
    workspace_id: int,
    provider_message_id: str,
    timestamp: datetime,
    category: MessageCategory | None,
    customer_id: int | None = None,
    parsed_metadata: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> None:
    stored = created_at or timestamp
    session.add(
        IngestedMessage(
            workspace_id=workspace_id,
            channel_type="whatsapp",
            provider_message_id=provider_message_id,
            raw_payload="{}",
            category=category,
            customer_id=customer_id,
            parsed_metadata=parsed_metadata,
            timestamp=timestamp,
            created_at=stored,
            updated_at=updated_at or stored,
        )
    )
    session.commit()


def test_dashboard_metrics_aggregate_workspace_messages(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    now = _utcnow()
    start = now - timedelta(days=1)
    end = now + timedelta(minutes=1)
    before = start - timedelta(days=2)
    other = Workspace(
        name="Other Kitchen Metrics",
        slug="other-kitchen-metrics",
        description="other",
        owner_id=workspace.owner_id,
        tenant_id=workspace.tenant_id,
        status=WorkspaceStatus.open,
    )
    session.add(other)
    session.commit()
    session.refresh(other)

    ada = _add_customer(
        session,
        workspace_id=workspace.id,
        name="Ada",
        phone="2348000000001",
        created_at=before,
    )
    bola = _add_customer(
        session,
        workspace_id=workspace.id,
        name="Bola",
        phone="2348000000002",
        created_at=now,
    )
    chi = _add_customer(
        session,
        workspace_id=workspace.id,
        name="Chi",
        phone="2348000000003",
        created_at=now,
    )
    stored = now - timedelta(seconds=30)
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="ada-old-order",
        timestamp=before,
        category=MessageCategory.order,
        customer_id=ada.id,
        parsed_metadata={"items": [{"name": "Jollof", "quantity": 1}]},
        created_at=before,
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="ada-enquiry",
        timestamp=now,
        category=MessageCategory.enquiry,
        customer_id=ada.id,
        created_at=stored,
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="ada-order",
        timestamp=now,
        category=MessageCategory.order,
        customer_id=ada.id,
        parsed_metadata={
            "items": [{"name": "Jollof", "quantity": 2}],
            "estimated_value": 5000,
            "manual_override": True,
        },
        created_at=stored,
        updated_at=stored + timedelta(seconds=10),
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="bola-enquiry",
        timestamp=now,
        category=MessageCategory.enquiry,
        customer_id=bola.id,
        created_at=stored,
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="chi-order",
        timestamp=now,
        category=MessageCategory.order,
        customer_id=chi.id,
        parsed_metadata={
            "items": [
                {"name": "Jollof", "quantity": 1},
                {"name": "Plantain", "quantity": 3, "unit_price": 100},
            ]
        },
        created_at=stored,
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="noise",
        timestamp=now,
        category=MessageCategory.ignore,
        created_at=stored,
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="unclassified",
        timestamp=now,
        category=None,
        created_at=stored,
    )
    _add_message(
        session,
        workspace_id=other.id,
        provider_message_id="other-order",
        timestamp=now,
        category=MessageCategory.order,
        parsed_metadata={"estimated_value": 99999, "items": [{"name": "Secret", "quantity": 4}]},
        created_at=stored,
    )

    response = client.get(
        _metrics_url(
            workspace.slug,
            query=f"start={start.isoformat()}&end={end.isoformat()}",
        ),
        headers=superuser_account_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["operational"]["total_leads_processed"] == 6
    assert body["operational"]["conversion_rate"] == 50
    assert body["operational"]["total_estimated_order_value"] == 5300
    assert body["operational"]["top_selling_items"] == [
        {"name": "Jollof", "count": 3},
        {"name": "Plantain", "count": 3},
    ]
    assert body["intent"] == {
        "order": 2,
        "enquiry": 2,
        "ignore": 1,
        "actionable_ratio": 0.6667,
    }
    assert body["customers"]["new_customers"] == 2
    assert body["customers"]["returning_customers"] == 1
    assert body["customers"]["manual_override_rate"] == 20
    assert body["customers"]["average_ai_processing_latency_seconds"] == 2


def test_dashboard_empty_period_guards_divide_by_zero(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    response = client.get(
        _metrics_url(workspace.slug, "period=today"),
        headers=superuser_account_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["operational"]["total_leads_processed"] == 0
    assert body["operational"]["conversion_rate"] == 0
    assert body["operational"]["total_estimated_order_value"] == 0
    assert body["operational"]["top_selling_items"] == []
    assert body["intent"]["actionable_ratio"] == 0
    assert body["customers"]["manual_override_rate"] == 0
    assert body["customers"]["average_ai_processing_latency_seconds"] == 0


def test_dashboard_period_query_limits_messages(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    now = _utcnow()
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="recent",
        timestamp=now,
        category=MessageCategory.enquiry,
    )
    _add_message(
        session,
        workspace_id=workspace.id,
        provider_message_id="stale",
        timestamp=now - timedelta(days=40),
        category=MessageCategory.order,
    )
    response = client.get(
        _metrics_url(workspace.slug, "period=7d"),
        headers=superuser_account_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["operational"]["total_leads_processed"] == 1
    assert response.json()["intent"]["enquiry"] == 1
    assert response.json()["intent"]["order"] == 0


def test_dashboard_rejects_inverted_range(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    _, workspace = _owned_workspace(session)
    response = client.get(
        _metrics_url(workspace.slug, "start=2026-02-02T00:00:00&end=2026-02-01T00:00:00"),
        headers=superuser_account_token_headers,
    )
    assert response.status_code == 422


def test_dashboard_requires_auth(client: TestClient, session: Session) -> None:
    _, workspace = _owned_workspace(session)
    response = client.get(_metrics_url(workspace.slug))
    assert response.status_code in {401, 403}


def test_dashboard_forbids_member_and_guest(
    client: TestClient,
    session: Session,
) -> None:
    _, workspace = _owned_workspace(session)
    for role, email_prefix in ((UserType.member, "member"), (UserType.guest, "guest")):
        _, headers = create_random_account_with_token(
            client,
            session,
            account_action,
            oauth_url=f"{settings.API_V1_STR}/login",
            email=f"{email_prefix}.dash@example.com",
            password="s3cret-pass",
        )
        account = account_action.get_by_email(session, email=f"{email_prefix}.dash@example.com")
        assert account is not None
        user_action.create_membership(
            session,
            account_id=account.id,
            workspace_id=workspace.id,
            owner_id=workspace.owner_id,
            membership_type=role,
        )
        response = client.get(_metrics_url(workspace.slug), headers=headers)
        assert response.status_code == 403


def test_dashboard_allows_admin(
    client: TestClient,
    session: Session,
) -> None:
    _, workspace = _owned_workspace(session)
    _, headers = create_random_account_with_token(
        client,
        session,
        account_action,
        oauth_url=f"{settings.API_V1_STR}/login",
        email="admin.dash@example.com",
        password="s3cret-pass",
    )
    account = account_action.get_by_email(session, email="admin.dash@example.com")
    assert account is not None
    user_action.create_membership(
        session,
        account_id=account.id,
        workspace_id=workspace.id,
        owner_id=workspace.owner_id,
        membership_type=UserType.admin,
    )
    response = client.get(_metrics_url(workspace.slug), headers=headers)
    assert response.status_code == 200
    assert "total_estimated_order_value" in response.json()["operational"]
