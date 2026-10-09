"""Worker classification, persistence, and idempotency."""

from sqlmodel import Session, func, select

from app.core.config import settings
from app.ingestion.pipeline import process_incoming_message
from app.ingestion.schema import ExtractedOrderItem, MessageExtraction
from app.models import Customer, IngestedMessage, Workspace
from app.worker import process_incoming_message_task


def _workspace_id(session: Session) -> int:
    workspace = session.exec(select(Workspace)).first()
    assert workspace is not None
    assert workspace.id is not None
    return workspace.id


def _whatsapp_order() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {"profile": {"name": "Ada"}, "wa_id": "2348012345678"}
                            ],
                            "messages": [
                                {
                                    "from": "2348012345678",
                                    "id": "wamid.ORDER1",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {
                                        "body": (
                                            "I want 2 plates of jollof rice. "
                                            "Deliver to Lekki phase 1"
                                        )
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }


def _meta_enquiry() -> dict:
    return {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "USER1"},
                        "recipient": {"id": "PAGE"},
                        "timestamp": 1710000000000,
                        "message": {"mid": "mid.ENQ1", "text": "Do you deliver to Ikeja?"},
                    }
                ]
            }
        ],
    }


def test_worker_classifies_order_and_is_idempotent(session: Session, monkeypatch) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("LLM should stay unused without a provider")

    monkeypatch.setattr("msflib.ai_core.deps.get_ai_dependencies", _boom)
    workspace_id = _workspace_id(session)
    payload = _whatsapp_order()

    first = process_incoming_message(
        session,
        workspace_id=workspace_id,
        channel_type="whatsapp",
        raw_payload=payload,
    )
    second = process_incoming_message(
        session,
        workspace_id=workspace_id,
        channel_type="whatsapp",
        raw_payload=payload,
    )

    assert first["status"] == "ok"
    assert first["ingested_message_ids"] == second["ingested_message_ids"]
    assert len(first["ingested_message_ids"]) == 1
    count = session.exec(select(func.count()).select_from(IngestedMessage)).one()
    assert count == 1

    row = session.get(IngestedMessage, first["ingested_message_ids"][0])
    assert row is not None
    assert str(row.category) == "order"
    assert row.provider_message_id == "wamid.ORDER1"
    assert row.channel_type == "whatsapp"
    assert row.sender == "2348012345678"
    metadata = row.parsed_metadata or {}
    assert metadata["items"][0]["quantity"] == 2
    assert "jollof" in metadata["items"][0]["name"]
    assert "Lekki" in metadata["delivery_hint"]

    customer = session.get(Customer, row.customer_id)
    assert customer is not None
    assert customer.name == "Ada"
    assert customer.phone == "2348012345678"


def test_worker_records_business_number_and_mixes_enquiry_with_order(session: Session) -> None:
    from scripts.simulate_whatsapp_webhook import MESSAGES, webhook_payload

    workspace_id = _workspace_id(session)
    categories = []
    for index, message in enumerate(MESSAGES):
        result = process_incoming_message(
            session,
            workspace_id=workspace_id,
            channel_type="whatsapp",
            raw_payload=webhook_payload(message, index=index),
        )
        row = session.get(IngestedMessage, result["ingested_message_ids"][0])
        assert row is not None
        assert row.display_phone_number == "2348095550100"
        categories.append(str(row.category))
    assert categories[0] == "enquiry"
    assert categories[1] == "order"
    assert "enquiry" in categories and "order" in categories


def test_worker_classifies_enquiry(session: Session) -> None:
    result = process_incoming_message(
        session,
        workspace_id=_workspace_id(session),
        channel_type="meta",
        raw_payload=_meta_enquiry(),
    )
    row = session.get(IngestedMessage, result["ingested_message_ids"][0])
    assert row is not None
    assert str(row.category) == "enquiry"
    metadata = row.parsed_metadata or {}
    assert metadata["topic"] == "delivery"
    assert "Ikeja" in metadata["question_summary"]
    customer = session.get(Customer, row.customer_id)
    assert customer is not None
    assert customer.handle == "USER1"


def test_worker_ignores_malformed_payload(session: Session) -> None:
    workspace_id = _workspace_id(session)
    result = process_incoming_message(
        session,
        workspace_id=workspace_id,
        channel_type="whatsapp",
        raw_payload="not-json",
    )
    missing_id = process_incoming_message(
        session,
        workspace_id=workspace_id,
        channel_type="whatsapp",
        raw_payload={"entry": [{"changes": [{"value": {"messages": [{"from": "1"}]}}]}]},
    )
    assert result["status"] == "ignored"
    assert missing_id["ingested_message_ids"] == []
    assert session.exec(select(IngestedMessage)).all() == []


def test_worker_uses_ai_core_registry_when_configured(session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-test")

    class _FakeStructured:
        def invoke(self, _messages):
            return MessageExtraction(
                category="order",
                items=[ExtractedOrderItem(name="jollof rice", quantity=1)],
            )

    class _FakeLLM:
        def with_structured_output(self, _schema):
            return _FakeStructured()

    calls: list[str] = []

    class _Deps:
        def get_llm_from_registry(self, _session, *, scope, task=None, **_kwargs):
            assert scope is not None
            calls.append(task)
            return _FakeLLM()

        def get_llm(self):
            raise AssertionError("registry already returned a model")

    monkeypatch.setattr("msflib.ai_core.deps.get_ai_dependencies", lambda _settings: _Deps())

    result = process_incoming_message(
        session,
        workspace_id=_workspace_id(session),
        channel_type="meta",
        raw_payload=_meta_enquiry(),
    )
    row = session.get(IngestedMessage, result["ingested_message_ids"][0])
    assert calls == ["socialchef.message_classify"]
    assert row is not None
    assert str(row.category) == "order"
    assert row.parsed_metadata["items"][0]["name"] == "jollof rice"


class _DummySession:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_celery_task_returns_error_instead_of_crashing(mocker) -> None:
    mocker.patch("sqlmodel.Session", return_value=_DummySession())
    mocker.patch(
        "app.ingestion.pipeline.process_incoming_message",
        side_effect=RuntimeError("database down"),
    )
    result = process_incoming_message_task(
        workspace_id=1,
        channel_type="whatsapp",
        raw_payload={"entry": []},
    )
    assert result == {"status": "error", "ingested_message_ids": []}
