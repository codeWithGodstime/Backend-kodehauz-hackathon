import os
import logging

from .db.init_db import init_db
from .db.session import Session, engine
from .bootstrap import bootstrap_module_hooks

bootstrap_module_hooks()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def should_reset_db() -> bool:
    return os.getenv("INITIAL_DATA_RESET_DB", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def init() -> None:
    with Session(engine):
        init_db(engine, create_tables=should_reset_db())


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
