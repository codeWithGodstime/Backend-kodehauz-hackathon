from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.billing.plan_cache import PLAN_CACHE_TTL_SECONDS, clear_subscription_plan_cache
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
    assert response.headers["cache-control"] == f"public, max-age={PLAN_CACHE_TTL_SECONDS}"


def test_subscription_plans_stay_cached_for_every_user(
    client: TestClient, session: Session
) -> None:
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
    session.commit()

    first = client.get(f"{settings.API_V1_STR}/billing/subscription-plans")
    assert first.status_code == 200
    assert first.json()[0]["plan_key"] == "free"

    for row in session.exec(select(SubscriptionPlan)).all():
        session.delete(row)
    session.commit()

    second = client.get(f"{settings.API_V1_STR}/billing/subscription-plans")
    assert second.status_code == 200
    assert second.json()[0]["plan_key"] == "free"

    clear_subscription_plan_cache()
    third = client.get(f"{settings.API_V1_STR}/billing/subscription-plans")
    assert third.status_code == 200
    assert third.json() == []
    assert third.headers["cache-control"] == "no-store"
