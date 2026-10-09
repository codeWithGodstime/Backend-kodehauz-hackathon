"""Classify inbound text as an order or an enquiry.

The worker calls ``msflib.ai_core.deps.get_ai_dependencies`` and uses
``get_llm_from_registry`` (task ``socialchef.message_classify``) or, if the
registry cannot build a client, ``get_llm``. Both go through AICoreSettings
and the provider registry. ``parse_llm_json`` repairs model JSON when
structured output is unavailable.

A vector store is not used. This app has no knowledge collection, and one
customer message is enough to classify.

Development fallback: when ``AICORE_LLM_API_KEY`` is empty and no active
ai_core provider profile is stored, keyword rules classify the message so
local runs still persist rows. The same rules run if a configured model
call fails, so a provider outage does not drop the webhook.
"""

import logging
import re
from typing import Any

from sqlalchemy import inspect
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.schema import ExtractedOrderItem, MessageExtraction

logger = logging.getLogger(__name__)

CLASSIFY_TASK = "socialchef.message_classify"

_ORDER_RE = re.compile(
    r"\b(order|buy|purchase|checkout|i want|i need|i'?d like|send me|"
    r"plate of|plates of|pack of|packs of|portion of)\b",
    re.IGNORECASE,
)
_QUESTION_START_RE = re.compile(
    r"^(do|does|did|can|could|what|when|where|who|why|how|is|are|will)\b",
    re.IGNORECASE,
)
_QTY_THEN_ITEM_RE = re.compile(
    r"(\d+)\s*(?:x|×)?\s+([A-Za-z][A-Za-z0-9 &'-]{1,60})",
)
_ITEM_THEN_QTY_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 &'-]{1,60})\s*(?:x|×)\s*(\d+)",
)
_DELIVERY_RE = re.compile(
    r"(?:deliver(?:y)?(?:\s+address)?(?:\s+to)?|send(?:\s+it)?\s+to|address)\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)
_TRAILING_JOIN_RE = re.compile(r"\s+\b(and|with|please)\b\s*$", re.IGNORECASE)
_TOPIC_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hours", re.compile(r"\b(open|close|closing|hours|time)\b", re.IGNORECASE)),
    ("price", re.compile(r"\b(price|cost|how much|rate)\b", re.IGNORECASE)),
    ("delivery", re.compile(r"\b(deliver|delivery|shipping)\b", re.IGNORECASE)),
    ("menu", re.compile(r"\b(menu|available|what do you (?:sell|have))\b", re.IGNORECASE)),
)


def classify_message(text: str, *, session: Session, workspace_id: int) -> MessageExtraction:
    cleaned = text.strip()
    if not cleaned:
        return MessageExtraction(category="ignore")
    llm = resolve_llm(session, workspace_id=workspace_id)
    if llm is None:
        return development_fallback_classify(cleaned)
    try:
        return _extract_with_llm(llm, cleaned)
    except Exception:
        logger.exception("LLM classification failed; using development fallback")
        return development_fallback_classify(cleaned)


def resolve_llm(session: Session, *, workspace_id: int) -> Any | None:
    """Return a chat model from ai_core, or None when nothing is configured."""
    ai_settings = settings.scope("AI_CORE").unwrap()
    has_key = bool(str(ai_settings.LLM_API_KEY or "").strip())
    if not has_key and not _has_llm_profile(session):
        return None

    from msflib.ai_core.deps import get_ai_dependencies
    from msflib.scope import build_context_scope
    from msflib.tenancy.resolver import resolve_default_tenant_id

    ai = get_ai_dependencies(settings)
    try:
        tenant_id = resolve_default_tenant_id(session, create_if_missing=False)
        if tenant_id is not None:
            scope = build_context_scope(tenant_id=tenant_id, workspace_id=workspace_id)
            return ai.get_llm_from_registry(
                session,
                scope=scope,
                task=CLASSIFY_TASK,
            )
    except Exception:
        logger.warning("LLM provider registry resolution failed", exc_info=True)
        session.rollback()
    if has_key:
        return ai.get_llm()
    return None


def development_fallback_classify(text: str) -> MessageExtraction:
    """Deterministic stand-in used only when no LLM provider is configured."""
    items = _extract_items(text)
    is_question = "?" in text or _QUESTION_START_RE.search(text) is not None
    is_order = _ORDER_RE.search(text) is not None or (bool(items) and not is_question)
    if is_order:
        return MessageExtraction(
            category="order",
            items=items,
            delivery_hint=_delivery_hint(text),
        )
    return MessageExtraction(
        category="enquiry",
        topic=_topic(text),
        question_summary=text.strip()[:500],
    )


def _extract_with_llm(llm: Any, text: str) -> MessageExtraction:
    from langchain_core.messages import HumanMessage, SystemMessage
    from msflib.ai_core.services.llm_json import parse_llm_json

    messages = [
        SystemMessage(
            content=(
                "You classify a customer message for a food business inbox. "
                'category is "order" when they are trying to buy, and "enquiry" '
                "when they are asking a question. For an order, fill items with "
                "name and quantity, and delivery_hint when a place is present. "
                "For an enquiry, fill topic with a short label and question_summary "
                "with one sentence. Use ignore only when there is no customer request."
            )
        ),
        HumanMessage(content=text),
    ]
    if hasattr(llm, "with_structured_output"):
        try:
            structured = llm.with_structured_output(MessageExtraction)
            result = structured.invoke(messages)
            if isinstance(result, MessageExtraction):
                return result
            if isinstance(result, dict):
                return MessageExtraction.model_validate(result)
        except Exception:
            logger.info("structured extraction failed; parsing JSON text", exc_info=True)

    response = llm.invoke(messages)
    parsed = parse_llm_json(_response_text(response))
    if not isinstance(parsed, dict):
        raise TypeError("LLM JSON was not an object")
    return MessageExtraction.model_validate(parsed)


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


def _has_llm_profile(session: Session) -> bool:
    if not settings.scope("AI_CORE").unwrap().DB_PROVIDER_REGISTRY_ENABLED:
        return False
    try:
        from msflib.ai_core.models.provider import AIProviderProfile
    except Exception:
        logger.debug("ai_core provider model is not importable", exc_info=True)
        return False

    table_name = str(AIProviderProfile.__tablename__)
    try:
        if not inspect(session.get_bind()).has_table(table_name):
            return False
        rows = session.exec(
            select(AIProviderProfile).where(AIProviderProfile.is_active.is_(True)).limit(20)
        ).all()
    except Exception:
        logger.debug("provider profile lookup skipped", exc_info=True)
        session.rollback()
        return False
    return any(getattr(row, "usage_kind", None) in {"llm", "both"} for row in rows)


def _extract_items(text: str) -> list[ExtractedOrderItem]:
    found: list[ExtractedOrderItem] = []
    seen: set[str] = set()
    for match in _QTY_THEN_ITEM_RE.finditer(text):
        _add_item(found, seen, name=match.group(2), quantity=int(match.group(1)))
    for match in _ITEM_THEN_QTY_RE.finditer(text):
        _add_item(found, seen, name=match.group(1), quantity=int(match.group(2)))
    return found[:20]


def _add_item(
    found: list[ExtractedOrderItem],
    seen: set[str],
    *,
    name: str,
    quantity: int,
) -> None:
    cleaned = _TRAILING_JOIN_RE.sub("", name).strip(" .,-")
    key = cleaned.lower()
    if len(cleaned) < 2 or key in seen or quantity < 1:
        return
    seen.add(key)
    found.append(ExtractedOrderItem(name=cleaned, quantity=quantity))


def _delivery_hint(text: str) -> str | None:
    match = _DELIVERY_RE.search(text.strip())
    if match is None:
        return None
    hint = match.group(1).strip(" .")
    if len(hint) > 160:
        hint = hint[:160].rstrip()
    return hint or None


def _topic(text: str) -> str:
    for label, pattern in _TOPIC_RULES:
        if pattern.search(text):
            return label
    return "general"
