import logging

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_broker_url() -> str:
    if settings.REDIS_HOST:
        password = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
        port = settings.REDIS_PORT or "6379"
        return f"redis://{password}{settings.REDIS_HOST}:{port}/0"
    return "memory://"


broker_url = get_broker_url()
celery_app = Celery("app.worker", broker=broker_url, backend=broker_url)
celery_app.conf.task_default_queue = "main-queue"


@celery_app.task(acks_late=True)
def test_celery(word: str) -> str:
    return f"test task return {word}"


@celery_app.task(acks_late=True)
def process_incoming_message_task(
    workspace_id: int,
    channel_type: str,
    raw_payload: dict,
) -> dict:
    """Classify a webhook payload after the HTTP handler has already returned."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.ingestion.pipeline import process_incoming_message

    try:
        with Session(engine) as session:
            return process_incoming_message(
                session,
                workspace_id=workspace_id,
                channel_type=channel_type,
                raw_payload=raw_payload,
            )
    except Exception:
        logger.exception(
            "incoming message task failed workspace_id=%s channel_type=%s",
            workspace_id,
            channel_type,
        )
        return {"status": "error", "ingested_message_ids": []}
