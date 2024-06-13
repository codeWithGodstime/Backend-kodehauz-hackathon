from sqlmodel import Session, create_engine  # noqa
from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    echo=settings.DB_DEBUG_MODE,
)
