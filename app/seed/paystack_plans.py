"""Create the Socialchef monthly plan on Paystack and store its plan code.

Usage:
    python -m app.seed.paystack_plans

Safe to re-run. An existing Paystack plan with the same name is reused.
"""

from __future__ import annotations

import sys

import httpx
from sqlmodel import Session, SQLModel, select

from app.core.config import settings
from app.db.session import engine
from app.models.socialchef import (
    FREE_PLAN_KEY,
    FREE_PLAN_NAME,
    PAID_MONTHLY_PLAN_KEY,
    PAID_MONTHLY_PLAN_NAME,
    SubscriptionPlan,
    SubscriptionTier,
)


def main() -> int:
    payments = settings.scope("PAYMENTS")
    secret = (payments.PAYSTACK_SECRET_KEY or "").strip()
    if not secret:
        print("PAYSTACK_SECRET_KEY is empty. Set it before seeding plans.")
        return 1
    if secret.startswith("sk_live_"):
        print("PAYSTACK_SECRET_KEY is a live key. This script was not run.")
        print(
            "Run `python -m app.seed.paystack_plans` yourself when you intend to create live plans."
        )
        return 2
    if not secret.startswith("sk_test_"):
        print("PAYSTACK_SECRET_KEY is not a test key (sk_test_). This script was not run.")
        return 2

    _save_free_plan(currency=settings.SOCIALCHEF_BILLING_CURRENCY or "NGN")

    amount_kobo = settings.SOCIALCHEF_BILLING_AMOUNT
    if amount_kobo is None or amount_kobo <= 0:
        print("SOCIALCHEF_BILLING_AMOUNT is not set. It must be the plan amount in kobo.")
        return 1

    currency = settings.SOCIALCHEF_BILLING_CURRENCY or "NGN"
    base_url = payments.PAYSTACK_BASE_URL.rstrip("/")
    existing = _find_plan(base_url, secret, PAID_MONTHLY_PLAN_NAME)
    if existing is None:
        existing = _create_plan(
            base_url,
            secret,
            name=PAID_MONTHLY_PLAN_NAME,
            amount_kobo=amount_kobo,
            currency=currency,
        )
        if existing is None:
            return 1
        print(f"Created Paystack plan {PAID_MONTHLY_PLAN_NAME}")
    else:
        print(f"Reusing Paystack plan {PAID_MONTHLY_PLAN_NAME}")
        remote_amount = existing.get("amount")
        if isinstance(remote_amount, int) and remote_amount > 0:
            amount_kobo = remote_amount

    plan_code = str(existing.get("plan_code") or "").strip()
    if not plan_code:
        print("Paystack did not return a plan_code.")
        return 1

    _save_plan(
        plan_code=plan_code,
        amount_kobo=amount_kobo,
        currency=str(existing.get("currency") or currency),
        interval=str(existing.get("interval") or "monthly"),
    )
    naira = amount_kobo / 100
    print(
        f"Stored {PAID_MONTHLY_PLAN_KEY} plan_code={plan_code} "
        f"amount={naira:.2f} {currency} ({amount_kobo} kobo)"
    )
    return 0


def _headers(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}


def _find_plan(base_url: str, secret: str, name: str) -> dict | None:
    page = 1
    with httpx.Client(timeout=30.0) as client:
        while page <= 20:
            response = client.get(
                f"{base_url}/plan",
                headers=_headers(secret),
                params={"perPage": 50, "page": page},
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(batch, list) or not batch:
                return None
            for plan in batch:
                if isinstance(plan, dict) and plan.get("name") == name:
                    return plan
            meta = payload.get("meta") if isinstance(payload, dict) else {}
            page_count = (meta or {}).get("pageCount")
            if isinstance(page_count, int) and page >= page_count:
                return None
            if len(batch) < 50:
                return None
            page += 1
    return None


def _create_plan(
    base_url: str,
    secret: str,
    *,
    name: str,
    amount_kobo: int,
    currency: str,
) -> dict | None:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base_url}/plan",
            headers=_headers(secret),
            json={
                "name": name,
                "interval": "monthly",
                "amount": amount_kobo,
                "currency": currency,
            },
        )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data.get("plan_code"):
        print("Paystack plan create returned no plan_code.")
        return None
    return data


def _save_free_plan(*, currency: str) -> None:
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        row = session.exec(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_key == FREE_PLAN_KEY)
        ).first()
        if row is None:
            row = SubscriptionPlan(
                plan_key=FREE_PLAN_KEY,
                name=FREE_PLAN_NAME,
                tier=SubscriptionTier.free,
                interval="none",
                amount_kobo=0,
                currency=currency,
                plan_code=None,
            )
        else:
            row.name = FREE_PLAN_NAME
            row.tier = SubscriptionTier.free
            row.interval = "none"
            row.amount_kobo = 0
            row.currency = currency
            row.plan_code = None
        session.add(row)
        session.commit()
    print(f"Stored {FREE_PLAN_KEY} amount=0 {currency}")


def _save_plan(*, plan_code: str, amount_kobo: int, currency: str, interval: str) -> None:
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        row = session.exec(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_key == PAID_MONTHLY_PLAN_KEY)
        ).first()
        if row is None:
            row = SubscriptionPlan(
                plan_key=PAID_MONTHLY_PLAN_KEY,
                name=PAID_MONTHLY_PLAN_NAME,
                tier=SubscriptionTier.paid,
                interval=interval,
                amount_kobo=amount_kobo,
                currency=currency,
                plan_code=plan_code,
            )
        else:
            row.name = PAID_MONTHLY_PLAN_NAME
            row.tier = SubscriptionTier.paid
            row.interval = interval
            row.amount_kobo = amount_kobo
            row.currency = currency
            row.plan_code = plan_code
        session.add(row)
        session.commit()


if __name__ == "__main__":
    sys.exit(main())
