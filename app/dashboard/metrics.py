"""Aggregate workspace dashboard metrics from ingested messages and customers.

Estimated order value reads optional monetary keys on ``parsed_metadata``
(``estimated_value``, ``total``, ``amount``, ``gross_value``, or item
``unit_price`` / ``price``). Classification stores item name and quantity
only, so the total stays 0 until a price is present.

Manual override rate counts classified messages whose ``parsed_metadata``
has ``manual_override`` or ``overridden`` set. There is no override column.

Processing latency averages ``updated_at - created_at`` on classified
messages. The worker classifies before insert, and webhook ingress time is
not stored, so those timestamps usually match.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.socialchef import Customer, IngestedMessage, MessageCategory

_VALUE_KEYS = ("estimated_value", "total", "amount", "gross_value")
_ITEM_PRICE_KEYS = ("unit_price", "price")
_TOP_ITEM_LIMIT = 10


class DashboardPeriodError(ValueError):
    """Raised when the requested reporting window is invalid."""


def resolve_window(
    period: str | None,
    start: datetime | None,
    end: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return an inclusive ``[start, end]`` window in naive UTC."""
    if start is not None or end is not None:
        if start is None or end is None:
            raise DashboardPeriodError("start and end are both required for a custom range")
        start_at = _naive_utc(start)
        end_at = _naive_utc(end)
        if end_at < start_at:
            raise DashboardPeriodError("end must be on or after start")
        return start_at, end_at

    current = _naive_utc(now) if now is not None else _utcnow()
    key = period or "7d"
    if key == "today":
        return current.replace(hour=0, minute=0, second=0, microsecond=0), current
    if key == "7d":
        return current - timedelta(days=7), current
    if key == "30d":
        return current - timedelta(days=30), current
    raise DashboardPeriodError("period must be today, 7d, or 30d")


def build_dashboard_metrics(
    session: Session,
    *,
    workspace_id: int,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    messages = list(
        session.exec(
            select(IngestedMessage).where(
                IngestedMessage.workspace_id == workspace_id,
                IngestedMessage.timestamp >= start,
                IngestedMessage.timestamp <= end,
            )
        ).all()
    )
    new_customers = session.exec(
        select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.created_at >= start,
            Customer.created_at <= end,
        )
    ).all()

    counts = Counter(_category_value(row.category) for row in messages)
    order_count = counts.get("order", 0)
    enquiry_count = counts.get("enquiry", 0)
    ignore_count = counts.get("ignore", 0)
    total = len(messages)
    classified = [row for row in messages if _category_value(row.category) is not None]
    enquiry_customers = _customer_ids(messages, "enquiry")
    order_customers = _customer_ids(messages, "order")
    converted = enquiry_customers & order_customers

    return {
        "period": {"start": start, "end": end},
        "operational": {
            "total_leads_processed": total,
            "conversion_rate": _percent(len(converted), len(enquiry_customers)),
            "total_estimated_order_value": round(
                sum(
                    _order_value(row)
                    for row in messages
                    if _category_value(row.category) == "order"
                ),
                2,
            ),
            "top_selling_items": _top_selling_items(messages),
        },
        "intent": {
            "order": order_count,
            "enquiry": enquiry_count,
            "ignore": ignore_count,
            "actionable_ratio": _ratio(order_count + enquiry_count, total),
        },
        "customers": {
            "new_customers": len(new_customers),
            "returning_customers": _returning_customers(
                session,
                workspace_id=workspace_id,
                messages=messages,
                start=start,
            ),
            "average_ai_processing_latency_seconds": _average_latency(classified),
            "manual_override_rate": _percent(
                sum(1 for row in classified if _is_manual_override(row.parsed_metadata)),
                len(classified),
            ),
        },
    }


def _returning_customers(
    session: Session,
    *,
    workspace_id: int,
    messages: list[IngestedMessage],
    start: datetime,
) -> int:
    in_period: Counter[int] = Counter()
    for row in messages:
        if _category_value(row.category) != "order" or row.customer_id is None:
            continue
        in_period[row.customer_id] += 1
    if not in_period:
        return 0

    earlier_rows = session.exec(
        select(IngestedMessage.customer_id).where(
            IngestedMessage.workspace_id == workspace_id,
            IngestedMessage.category == MessageCategory.order,
            IngestedMessage.customer_id.in_(list(in_period)),  # type: ignore[union-attr]
            IngestedMessage.timestamp < start,
        )
    ).all()
    earlier = {customer_id for customer_id in earlier_rows if customer_id is not None}
    return sum(1 for customer_id, count in in_period.items() if count >= 2 or customer_id in earlier)


def _top_selling_items(messages: list[IngestedMessage]) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for row in messages:
        if _category_value(row.category) != "order":
            continue
        metadata = row.parsed_metadata if isinstance(row.parsed_metadata, dict) else {}
        items = metadata.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            key = name.casefold()
            labels.setdefault(key, name)
            quantity = _number(item.get("quantity"))
            units = int(quantity) if quantity is not None and quantity > 0 else 1
            totals[key] += units
    ranked = sorted(totals, key=lambda key: (-totals[key], labels[key].casefold()))
    return [{"name": labels[key], "count": totals[key]} for key in ranked[:_TOP_ITEM_LIMIT]]


def _order_value(row: IngestedMessage) -> float:
    metadata = row.parsed_metadata if isinstance(row.parsed_metadata, dict) else None
    if metadata is None:
        return 0.0
    for key in _VALUE_KEYS:
        amount = _number(metadata.get(key))
        if amount is not None:
            return amount
    items = metadata.get("items")
    if not isinstance(items, list):
        return 0.0
    total = 0.0
    found = False
    for item in items:
        if not isinstance(item, dict):
            continue
        price = _item_price(item)
        if price is None:
            continue
        quantity = _number(item.get("quantity"))
        units = quantity if quantity is not None and quantity > 0 else 1.0
        total += price * units
        found = True
    return total if found else 0.0


def _item_price(item: dict[str, Any]) -> float | None:
    for key in _ITEM_PRICE_KEYS:
        price = _number(item.get(key))
        if price is not None:
            return price
    return None


def _average_latency(messages: list[IngestedMessage]) -> float:
    samples: list[float] = []
    for row in messages:
        if row.created_at is None or row.updated_at is None:
            continue
        delta = (_naive_utc(row.updated_at) - _naive_utc(row.created_at)).total_seconds()
        if delta >= 0:
            samples.append(delta)
    if not samples:
        return 0.0
    return round(sum(samples) / len(samples), 2)


def _is_manual_override(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    flag = metadata.get("manual_override")
    if flag is None:
        flag = metadata.get("overridden")
    return flag is True or flag == 1


def _customer_ids(messages: list[IngestedMessage], category: str) -> set[int]:
    return {
        row.customer_id
        for row in messages
        if row.customer_id is not None and _category_value(row.category) == category
    }


def _category_value(category: Any) -> str | None:
    if category is None:
        return None
    value = getattr(category, "value", category)
    text = str(value).strip().lower()
    return text or None


def _percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
