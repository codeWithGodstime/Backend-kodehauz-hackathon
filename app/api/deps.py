from typing import Generator

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError

from app import actions, models, schemas
from app.core import security, store
from app.core.config import settings
from app.db.session import Session, engine

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login")
anonymous_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login", auto_error=False)


def get_session() -> Generator:
    with Session(engine) as session:
        yield session


def get_keystore() -> store.StoreInterface:
    if settings.REDIS_HOST and settings.REDIS_PASSWORD:
        return store.RedisStore(
            host=settings.REDIS_HOST, password=settings.REDIS_PASSWORD, port=settings.REDIS_PORT
        )
    else:
        return store.MapStore()


def get_current_account(
    session: Session = Depends(get_session),
    token: str = Depends(reusable_oauth2),
    keystore: store.StoreInterface = Depends(get_keystore),
) -> models.Account:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = schemas.TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
        )
    if keystore.check(token_data.sub):
        raise HTTPException(status_code=401, detail="Token expired")

    user = session.get(models.Account, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    return user


def get_current_account_or_none(
    session: Session = Depends(get_session),
    token: str = Depends(anonymous_oauth2),
    keystore: store.StoreInterface = Depends(get_keystore),
) -> models.Account:
    if token:
        return get_current_account(session, token, keystore)

    return None


def get_current_active_account(
    account: models.Account = Depends(get_current_account),
) -> models.Account:
    if account.status not in [
        models.account.AccountStatus.active,
        models.account.AccountStatus.online,
    ]:
        raise HTTPException(status_code=401, detail="The account is inactive")
    return account


def get_current_active_superuser(
    account: models.Account = Depends(get_current_active_account),
) -> models.Account:
    if not account.role == models.account.AccountRole.root:
        raise HTTPException(status_code=401, detail="Not authorized")
    return account
