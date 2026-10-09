"""Workspace dashboard metrics. Owner and admin memberships only."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from msflib.models import SchemaBase
from sqlmodel import Session

from app import models
from app.api import deps
from app.dashboard.metrics import DashboardPeriodError, build_dashboard_metrics, resolve_window

router = APIRouter()


class DashboardPeriodRead(SchemaBase):
    start: datetime
    end: datetime


class TopSellingItemRead(SchemaBase):
    name: str
    count: int


class OperationalMetricsRead(SchemaBase):
    total_leads_processed: int
    conversion_rate: float
    total_estimated_order_value: float
    top_selling_items: list[TopSellingItemRead]


class IntentMetricsRead(SchemaBase):
    order: int
    enquiry: int
    ignore: int
    actionable_ratio: float


class CustomerMetricsRead(SchemaBase):
    new_customers: int
    returning_customers: int
    average_ai_processing_latency_seconds: float
    manual_override_rate: float


class DashboardMetricsRead(SchemaBase):
    period: DashboardPeriodRead
    operational: OperationalMetricsRead
    intent: IntentMetricsRead
    customers: CustomerMetricsRead


_dashboard_role = deps.WorkspaceRoleCheck([models.UserType.owner, models.UserType.admin])


@router.get(
    "/{workspace_slug}/dashboard/metrics",
    response_model=DashboardMetricsRead,
    dependencies=[Depends(_dashboard_role)],
)
def read_dashboard_metrics(
    period: Literal["today", "7d", "30d"] = "7d",
    start: datetime | None = None,
    end: datetime | None = None,
    session: Session = Depends(deps.get_session),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> dict:
    try:
        window_start, window_end = resolve_window(period, start, end)
    except DashboardPeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return build_dashboard_metrics(
        session,
        workspace_id=workspace.id,
        start=window_start,
        end=window_end,
    )
