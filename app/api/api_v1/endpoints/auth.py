from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from typing_extensions import Annotated

from app import actions, models, schemas
from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.store import StoreInterface
from app.utils import (
    generate_password_reset_token,
    send_reset_password_email,
    verify_password_reset_token,
)

router = APIRouter()

CommonSession = Annotated[Session, Depends(deps.get_session)]


@router.post("/login", response_model=schemas.Token)
def login_access_token(
    session: CommonSession,
    form: OAuth2PasswordRequestForm = Depends(),
    token_store: StoreInterface = Depends(deps.get_keystore),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    account = actions.account.authenticate(
        session, email=form.username.lower(), password=form.password
    )
    if not account:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not models.account.AccountStatus.isActive(account.status):
        raise HTTPException(status_code=400, detail="Inactive account")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    account.last_login_date = datetime.now()
    session.add(account)
    session.commit()
    token_store.remove(account.id)
    return {
        "access_token": security.create_access_token(
            account.id, expires_delta=access_token_expires
        ),
        "expires": datetime.now() + access_token_expires,
        "token_type": "bearer",
        "account": account,
    }


@router.post("/test-access-token", response_model=models.Account)
def test_token(current_account: models.Account = Depends(deps.get_current_account)) -> Any:
    """
    Test access token
    """
    return current_account


@router.post("/password-recovery", response_model=schemas.Msg)
def recover_password(session: CommonSession, email: str = Body(..., embed=True)) -> Any:
    """
    Password Recovery
    """
    account = actions.account.get_by_email(session=session, email=email.lower())

    if not account:
        raise HTTPException(
            status_code=404,
            detail="The account with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email.lower())
    send_reset_password_email(
        email_to=account.email, username=account.username, token=password_reset_token
    )
    return {"msg": "Password recovery email sent"}


@router.post("/reset-password", response_model=schemas.Msg)
def reset_password(
    session: CommonSession,
    token: str = Body(...),
    new_password: str = Body(...),
) -> Any:
    """
    Reset password
    """
    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    account = actions.account.get_by_email(session=session, email=email)
    if not account:
        raise HTTPException(
            status_code=404,
            detail="The account with this username does not exist in the system.",
        )
    elif not models.account.AccountStatus.isActive(account.status):
        raise HTTPException(status_code=400, detail="Inactive account")
    hashed_password = get_password_hash(new_password)
    account.hashed_password = hashed_password
    session.add(account)
    session.commit()
    return {"msg": "Password updated successfully"}


@router.delete("/logout")
def logout(
    current_account: models.Account = Depends(deps.get_current_account),
    token_store: StoreInterface = Depends(deps.get_keystore),
) -> None:
    security.revoke_access_token(token_store, current_account.id)
