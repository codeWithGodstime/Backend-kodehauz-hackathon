import logging

from app.db.init_db import init_db
from app.db.session import Session, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine):
        # @todo Use typer to make this commandline arguments.
        init_db(engine, True)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
