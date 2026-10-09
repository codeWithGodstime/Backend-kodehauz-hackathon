"""One catalog snapshot for every user. Plans change only when they are seeded."""

import time
from threading import Lock

from sqlmodel import Session, select

from app.models.socialchef import SubscriptionPlan

PLAN_CACHE_TTL_SECONDS = 60 * 60 * 24

_lock = Lock()
_cached_at = 0.0
_plans: list[SubscriptionPlan] | None = None


def clear_subscription_plan_cache() -> None:
    global _cached_at, _plans
    with _lock:
        _cached_at = 0.0
        _plans = None


def plan_cache_control(has_plans: bool) -> str:
    if not has_plans:
        return "no-store"
    return f"public, max-age={PLAN_CACHE_TTL_SECONDS}"


def cached_subscription_plans(session: Session) -> list[SubscriptionPlan]:
    cached = _read()
    if cached is not None:
        return cached
    loaded = _load(session)
    if not loaded:
        return []
    _store(loaded)
    return list(loaded)


def _read() -> list[SubscriptionPlan] | None:
    with _lock:
        if _plans is None:
            return None
        if time.monotonic() - _cached_at >= PLAN_CACHE_TTL_SECONDS:
            return None
        return list(_plans)


def _store(plans: list[SubscriptionPlan]) -> None:
    global _cached_at, _plans
    with _lock:
        _plans = plans
        _cached_at = time.monotonic()


def _load(session: Session) -> list[SubscriptionPlan]:
    rows = list(
        session.exec(select(SubscriptionPlan).order_by(SubscriptionPlan.amount_kobo)).all()
    )
    for row in rows:
        session.expunge(row)
    return rows
