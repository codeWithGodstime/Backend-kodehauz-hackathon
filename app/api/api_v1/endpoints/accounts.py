from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing_extensions import Annotated

from app import actions, models
from app.api import deps
from app.core.config import settings
from app.utils import send_new_account_email

router = APIRouter()

CommonSession = Annotated[Session, Depends(deps.get_session)]


@router.get("/me", response_model=models.AccountRead)
def read_account_me(
    session: CommonSession,
    current_account: models.Account = Depends(deps.get_current_account),
) -> Any:
    """
    Get current account.
    """
    return current_account


@router.put("/me", response_model=models.AccountRead)
def update_account_me(
    *,
    session: CommonSession,
    account: models.AccountUpdate,
    current_account: models.Account = Depends(deps.get_current_account),
) -> models.Account:
    """
    Update own account.
    """
    account = actions.account.update(session=session, model=current_account, data=account)
    return account


@router.post("/open", response_model=models.AccountRead, status_code=201)
def create_account_open(
    *,
    session: CommonSession,
    data: models.UserProfile
) -> models.Account:
    """
    Create new account without the need to be logged in.
    """
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open account registration is forbidden on this server",
        )
    account = actions.account.get_by_any(
        session=session,
        username=data.account.username,
        email=data.account.email,
        phone=data.account.phone,
    )
    if account:
        raise HTTPException(
            status_code=400,
            detail="An account with this username, phone or email already exists in the system",
        )

    profile = models.Profile.from_orm(data.profile, update={"id": account.id})
    # userinfo = models.UserInfo.from_orm(data.info, update={"id": user.id})
    session.add(profile)
    # session.add(userinfo)

    # if data.type == models.user.UserType.learner.value:
    #     student = models.Student.from_orm(data.student, update={"id": user.id})
    #     session.add(student)
    # elif data.type == models.user.UserType.trainer.value:
    #     trainer = models.Trainer.from_orm(data.trainer, update={"id": user.id})
    #     session.add(trainer)

    session.commit()
    session.refresh(account)
    if settings.EMAILS_ENABLED:
        send_new_account_email(
            email_to=account.email, username=account.username, password=data.account.password
        )

    return account
