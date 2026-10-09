"""Start a paid checkout through msflib and grant access after verify."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx
from msflib.payments.models import PaymentData
from msflib.payments.service.error import PaymentAmountError, PaymentError
from msflib.payments.service.processor import process_payment
from msflib.workspaces.models.workspace import Workspace
from sqlmodel import Session, select

from app.billing.gateway import install_plan_gateway
from app.billing.plan_cache import cached_subscription_plans
from app.billing.plan_context import paystack_plan_code
from app.core.config import settings
from app.models.socialchef import (
    PAID_MONTHLY_PLAN_KEY,
    SubscriptionPlan,
    SubscriptionTier,
    WorkspaceSubscription,
)

logger = logging.getLogger(__name__)


class PlanNotSeeded(PaymentError):
    """Raised when checkout runs before the Paystack plan seed."""


class UnknownPlan(PaymentError):
    """Raised when checkout names a plan_code that is not in the catalog."""


class PlanNotBillable(PaymentError):
    """Raised when checkout is started for the free catalog plan."""


QUEUE_EVENT_KEY = "socialchef-subscription"


def kobo_to_major(amount_kobo: int) -> float:
    """Convert subunit (kobo) to the major units ``PaymentData.amount`` expects."""
    if amount_kobo <= 0:
        raise PaymentAmountError(
            "Amount must be greater than zero",
            cause=f"Invalid payment amount: {amount_kobo}",
        )
    major = (Decimal(amount_kobo) / Decimal(100)).quantize(Decimal("0.01"))
    return float(major)


def list_subscription_plans(session: Session) -> list[SubscriptionPlan]:
    return cached_subscription_plans(session)


def get_paid_monthly_plan(session: Session) -> SubscriptionPlan | None:
    return _plan_matching(session, plan_key=PAID_MONTHLY_PLAN_KEY)


def get_plan_by_code(session: Session, plan_code: str) -> SubscriptionPlan | None:
    code = plan_code.strip()
    if not code:
        return None
    return _plan_matching(session, plan_code=code)


def get_plan_by_key(session: Session, plan_key: str) -> SubscriptionPlan | None:
    key = plan_key.strip()
    if not key:
        return None
    return _plan_matching(session, plan_key=key)


def _plan_matching(
    session: Session,
    *,
    plan_key: str | None = None,
    plan_code: str | None = None,
) -> SubscriptionPlan | None:
    for plan in cached_subscription_plans(session):
        if plan_key is not None and plan.plan_key == plan_key:
            return plan
        if plan_code is not None and plan.plan_code == plan_code:
            return plan
    return None


def signup_plan_selection(session: Session, data: Any) -> dict[str, Any]:
    """Plan choice carried on open registration.

    ``skip_plan`` or a missing ``plan_key`` finishes signup on the free path.
    A ``plan_key`` must match the catalog. This does not start a charge or
    grant paid access; checkout stays on the billing route.
    """
    skip = bool(_signup_value(data, "skip_plan"))
    raw_key = _signup_value(data, "plan_key")
    plan_key = raw_key.strip() if isinstance(raw_key, str) else ""
    if skip or not plan_key:
        return {"skip_plan": True, "plan_key": None, "plan_code": None}

    plan = get_plan_by_key(session, plan_key)
    if plan is None:
        raise UnknownPlan("Subscription plan not found")
    return {
        "skip_plan": False,
        "plan_key": plan.plan_key,
        "plan_code": plan.plan_code,
    }


def _signup_value(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


async def start_subscription_checkout(
    session: Session,
    *,
    account: Any,
    workspace_id: int,
    email: str,
    plan_code: str | None = None,
) -> Any:
    """Create a Paystack checkout for a catalog plan.

    ``plan_code`` is the value stored when the Paystack plan was seeded. It is
    sent as Paystack's ``plan`` field on transaction initialize.
    """
    install_plan_gateway()
    payer_email = email.strip()
    if not payer_email:
        raise PaymentError("A customer email is required to start the charge")

    if plan_code and plan_code.strip():
        plan = get_plan_by_code(session, plan_code)
        if plan is None:
            raise UnknownPlan("Subscription plan not found")
    else:
        plan = get_paid_monthly_plan(session)
    if plan is None:
        raise PlanNotSeeded(
            "Paid monthly plan is not seeded. Run python -m app.seed.paystack_plans"
        )
    if plan.tier == SubscriptionTier.free or plan.amount_kobo <= 0:
        raise PlanNotBillable("The free plan does not require payment")
    if not plan.plan_code:
        raise PlanNotSeeded(
            "Paid monthly plan is not seeded. Run python -m app.seed.paystack_plans"
        )

    token = paystack_plan_code.set(plan.plan_code)
    try:
        return await process_payment(
            session=session,
            payment_data=PaymentData(
                email=payer_email,
                amount=kobo_to_major(plan.amount_kobo),
                gateway="paystack",
                description=plan.name,
                callback_url=settings.PAYMENT_CALLBACK_URL or None,
            ),
            account=account,
            settings=settings,
            queue_event_key=QUEUE_EVENT_KEY,
            queue_data={
                "workspace_id": workspace_id,
                "plan_code": plan.plan_code,
                "plan_key": plan.plan_key,
            },
        )
    finally:
        paystack_plan_code.reset(token)


async def fulfil_paid_subscription(queue: Any, session: Session) -> None:
    """Grant paid access. The router commits; this function must not."""
    payload = queue.data or {}
    workspace_id = payload.get("workspace_id")
    plan_code = payload.get("plan_code")
    if not isinstance(workspace_id, int) or workspace_id <= 0 or not plan_code:
        raise PaymentError("Payment queue is missing workspace_id or plan_code")
    if session.get(Workspace, workspace_id) is None:
        raise PaymentError(f"Workspace {workspace_id} was not found")

    payment = queue.payment
    reference = getattr(payment, "reference", None)
    if not reference:
        raise PaymentError("Verified payment has no reference")

    row = _get_or_create_subscription(session, workspace_id)
    if row.last_charge_reference == reference:
        return

    customer = await _customer_from_paystack(str(reference))
    row.tier = SubscriptionTier.paid
    row.plan_code = str(plan_code)
    row.gateway_customer_email = customer.get("email") or getattr(payment, "email", None)
    if customer.get("customer_code"):
        row.gateway_customer_code = str(customer["customer_code"])[:255]
    _store_card(row, customer.get("authorization") or {})
    _extend_paid_period(row)
    row.last_charge_reference = str(reference)[:100]
    session.add(row)


def _get_or_create_subscription(session: Session, workspace_id: int) -> WorkspaceSubscription:
    row = session.exec(
        select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
    ).first()
    if row is None:
        row = WorkspaceSubscription(workspace_id=workspace_id, tier=SubscriptionTier.free)
        session.add(row)
        session.flush()
    return row


def _extend_paid_period(row: WorkspaceSubscription) -> None:
    days = settings.SOCIALCHEF_SUBSCRIPTION_PERIOD_DAYS
    if days <= 0:
        raise PaymentError("SOCIALCHEF_SUBSCRIPTION_PERIOD_DAYS must be positive")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    anchor = row.subscription_expires_at
    if anchor is None or anchor < now:
        anchor = now
    row.subscription_expires_at = anchor + timedelta(days=days)


def _store_card(row: WorkspaceSubscription, authorization: dict[str, Any]) -> None:
    if not isinstance(authorization, dict):
        return
    reusable = authorization.get("reusable")
    row.authorization_reusable = reusable is True or (
        isinstance(reusable, str) and reusable.strip().lower() == "true"
    )
    if row.authorization_reusable:
        code = authorization.get("authorization_code")
        if code:
            row.authorization_code = str(code).strip()[:255]
    signature = authorization.get("signature")
    if signature:
        row.authorization_signature = str(signature).strip()[:255]
    brand = authorization.get("brand") or authorization.get("card_type")
    if brand:
        row.card_brand = str(brand).strip()[:64]
    last4 = authorization.get("last4")
    if last4:
        row.card_last4 = str(last4).strip()[:8]
    exp_month = authorization.get("exp_month")
    if exp_month:
        row.card_exp_month = str(exp_month).strip()[:2]
    exp_year = authorization.get("exp_year")
    if exp_year:
        row.card_exp_year = str(exp_year).strip()[:4]


async def _customer_from_paystack(reference: str) -> dict[str, Any]:
    """Read customer fields msflib drops because VerificationResult has no raw payload."""
    payments = settings.scope("PAYMENTS")
    secret = payments.PAYSTACK_SECRET_KEY
    if not secret:
        return {}
    url = f"{payments.PAYSTACK_BASE_URL}/transaction/verify/{quote(reference, safe='')}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=10.0)) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {secret}"})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("Could not read Paystack customer for reference %s", reference)
        return {}
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return {}
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    authorization = data.get("authorization") if isinstance(data.get("authorization"), dict) else {}
    return {
        "email": customer.get("email"),
        "customer_code": customer.get("customer_code"),
        "authorization": authorization,
    }
