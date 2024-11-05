from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from app import actions, models
from app.core.config import settings

# make sure all SQL Alchemy models are imported (app.models) before initializing DB
# otherwise, SQL Alchemy might fail to initialize relationships properly
# for more details: https://github.com/tiangolo/full-stack-fastapi-postgresql/issues/28


def init_db(engine: Engine, create_tables=False) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, specify True.
    if create_tables:
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        account = actions.account.get_by_email(session, email=settings.FIRST_SUPERUSER)
        if not account:
            data = models.AccountCreate(
                username=settings.FIRST_SUPERUSER,
                email=settings.FIRST_SUPERUSER,
                phone="",
                password=settings.FIRST_SUPERUSER_PASSWORD,
                status=models.account.AccountStatus.active,
                role=models.account.AccountRole.admin,
                profile=models.ProfileCreate(first_name="Super", last_name="User"),
            )
            account = actions.account.create(session, data=data)  # noqa: F841
