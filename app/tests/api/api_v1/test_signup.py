from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models.socialchef import SubscriptionPlan, SubscriptionTier, WorkspaceSubscription


def _enable_open_registration():
    account_settings = settings.scope("ACCOUNT")
    previous = account_settings.USERS_OPEN_REGISTRATION
    account_settings.USERS_OPEN_REGISTRATION = True
    return account_settings, previous


def _account_body(**extra: object) -> dict[str, object]:
    suffix = uuid4().hex[:10]
    body: dict[str, object] = {
        "username": f"chef{suffix}",
        "email": f"chef{suffix}@example.com",
        "phone": f"+2348{suffix[:8]}",
        "password": "s3cret-pass",
    }
    body.update(extra)
    return body


def _seed_plans(session: Session) -> None:
    session.add(
        SubscriptionPlan(
            plan_key="free",
            name="Socialchef Free",
            tier=SubscriptionTier.free,
            interval="none",
            amount_kobo=0,
            currency="NGN",
            plan_code=None,
        )
    )
    session.add(
        SubscriptionPlan(
            plan_key="paid_monthly",
            name="Socialchef Paid Monthly",
            tier=SubscriptionTier.paid,
            interval="monthly",
            amount_kobo=500000,
            currency="NGN",
            plan_code="PLN_test",
        )
    )
    session.commit()


def test_open_registration_skip_plan_issues_a_session(client: TestClient, session: Session) -> None:
    account_settings, previous = _enable_open_registration()
    try:
        _seed_plans(session)
        body = _account_body(skip_plan=True)
        created = client.post(f"{settings.API_V1_STR}/open", json=body)
        assert created.status_code == 201
        onboarding = created.json()["data"]["onboarding"]
        assert onboarding["skip_plan"] is True
        assert onboarding["plan_key"] is None
        assert onboarding["plan_code"] is None
        assert session.exec(select(WorkspaceSubscription)).first() is None

        logged_in = client.post(
            f"{settings.API_V1_STR}/login",
            data={"username": body["email"], "password": body["password"]},
        )
        assert logged_in.status_code == 200
        token = logged_in.json()["access_token"]
        me = client.get(
            f"{settings.API_V1_STR}/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == body["email"]
    finally:
        account_settings.USERS_OPEN_REGISTRATION = previous


def test_open_registration_stores_selected_plan_without_charging(
    client: TestClient, session: Session
) -> None:
    account_settings, previous = _enable_open_registration()
    try:
        _seed_plans(session)
        body = _account_body(plan_key="paid_monthly", skip_plan=False)
        created = client.post(f"{settings.API_V1_STR}/open", json=body)
        assert created.status_code == 201
        onboarding = created.json()["data"]["onboarding"]
        assert onboarding == {
            "skip_plan": False,
            "plan_key": "paid_monthly",
            "plan_code": "PLN_test",
        }
        assert session.exec(select(WorkspaceSubscription)).first() is None
    finally:
        account_settings.USERS_OPEN_REGISTRATION = previous


def test_open_registration_rejects_unknown_plan(client: TestClient, session: Session) -> None:
    account_settings, previous = _enable_open_registration()
    try:
        _seed_plans(session)
        body = _account_body(plan_key="does_not_exist", skip_plan=False)
        created = client.post(f"{settings.API_V1_STR}/open", json=body)
        assert created.status_code == 422
        assert created.json()["detail"] == "Subscription plan not found"
        me = client.post(
            f"{settings.API_V1_STR}/login",
            data={"username": body["email"], "password": body["password"]},
        )
        assert me.status_code != 200
    finally:
        account_settings.USERS_OPEN_REGISTRATION = previous
