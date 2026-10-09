from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models.socialchef import SubscriptionPlan, SubscriptionTier


def test_list_subscription_plans_is_public(client: TestClient, session: Session) -> None:
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

    response = client.get(f"{settings.API_V1_STR}/billing/subscription-plans")
    body = response.json()

    assert response.status_code == 200
    assert len(body) == 2
    assert body[0]["plan_key"] == "free"
    assert body[0]["tier"] == "free"
    assert body[0]["amount_kobo"] == 0
    assert body[0]["plan_code"] is None
    assert body[1]["plan_key"] == "paid_monthly"
    assert body[1]["name"] == "Socialchef Paid Monthly"
    assert body[1]["tier"] == "paid"
    assert body[1]["interval"] == "monthly"
    assert body[1]["amount_kobo"] == 500000
    assert body[1]["currency"] == "NGN"
    assert body[1]["plan_code"] == "PLN_test"
