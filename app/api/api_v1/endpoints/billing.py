"""Workspace checkout. Verification is the msflib payments route."""

from fastapi import APIRouter, Depends, HTTPException, Response
from msflib.models import SchemaBase
from msflib.payments.service.error import PaymentError
from sqlmodel import Session

from app import models
from app.actions import user_action
from app.api import deps
from app.billing.plan_cache import plan_cache_control
from app.billing.subscriptions import (
    PlanNotBillable,
    PlanNotSeeded,
    UnknownPlan,
    list_subscription_plans,
    start_subscription_checkout,
)

router = APIRouter()


class SubscriptionPlanRead(SchemaBase):
    id: int
    plan_key: str
    name: str
    tier: str
    interval: str
    amount_kobo: int
    currency: str
    plan_code: str | None = None


class SubscriptionCheckoutRequest(SchemaBase):
    email: str | None = None
    plan_code: str | None = None


class SubscriptionCheckoutResponse(SchemaBase):
    authorization_url: str
    access_code: str
    reference: str


@router.get("/subscription-plans", response_model=list[SubscriptionPlanRead])
def read_subscription_plans(
    response: Response,
    session: Session = Depends(deps.get_session),
) -> list[SubscriptionPlanRead]:
    plans = []
    for plan in list_subscription_plans(session):
        if plan.id is None:
            continue
        plans.append(
            SubscriptionPlanRead(
                id=plan.id,
                plan_key=plan.plan_key,
                name=plan.name,
                tier=plan.tier.value,
                interval=plan.interval,
                amount_kobo=plan.amount_kobo,
                currency=plan.currency,
                plan_code=plan.plan_code,
            )
        )
    response.headers["Cache-Control"] = plan_cache_control(bool(plans))
    return plans


@router.post("/workspaces/{workspace_id}/checkout", response_model=SubscriptionCheckoutResponse)
async def start_checkout(
    workspace_id: int,
    body: SubscriptionCheckoutRequest,
    session: Session = Depends(deps.get_session),
    account: models.Account = Depends(deps.get_current_account),
) -> SubscriptionCheckoutResponse:
    workspace = session.get(models.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    membership = user_action.get_by_all(session, account_id=account.id, workspace_id=workspace_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    email = (body.email or account.email or "").strip()
    if not email:
        raise HTTPException(status_code=422, detail="A customer email is required")
    try:
        payment = await start_subscription_checkout(
            session,
            account=account,
            workspace_id=workspace_id,
            email=email,
            plan_code=body.plan_code,
        )
    except UnknownPlan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlanNotBillable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlanNotSeeded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PaymentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SubscriptionCheckoutResponse(
        authorization_url=payment.authorization_url,
        access_code=payment.access_code or "",
        reference=payment.reference,
    )
