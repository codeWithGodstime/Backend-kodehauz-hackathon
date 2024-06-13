from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing_extensions import Annotated

from app import actions, models
from app.api import deps, rbac
from app.core.config import settings
from app.utils import send_new_account_email

router = APIRouter()

CommonSession = Annotated[Session, Depends(deps.get_session)]


@router.get("/", response_model=List[models.AccountRead])
def list_accounts(
    session: CommonSession,
    offset: int = 0,
    limit: int = 100,
    access: bool = Depends(rbac.RoleCheck(roles=[models.account.AccountRole.admin])),
) -> Any:
    """
    Retrieve current account.
    """
    return actions.account.get_multi(session, offset=offset, limit=limit)


@router.post("/", response_model=models.AccountRead, status_code=201)
def create_account(
    *,
    session: CommonSession,
    data: models.AccountCreate,
    access: bool = Depends(rbac.RoleCheck(roles=[models.account.AccountRole.admin])),
) -> Any:
    """
    Create new account.
    """
    account = actions.account.get_by_any(
        session=session,
        username=data.username,
        email=data.email,
        phone=data.phone,
    )
    if account:
        raise HTTPException(
            status_code=422,
            detail="A account with this username, phone or email already exists in the system.",
        )
    account = actions.account.create(session=session, data=data)
    if settings.EMAILS_ENABLED and data.email:
        send_new_account_email(email_to=data.email, username=data.email, password=data.password)
    return account


@router.put("/{account_id}", response_model=models.AccountRead)
def update_account(
    *,
    account_id: int,
    session: CommonSession,
    data: models.AccountUpdate,
    access: bool = Depends(rbac.RoleCheck(roles=[models.account.AccountRole.admin])),
) -> models.Account:
    """
    Update an account.
    """
    account = actions.account.get(session, id=account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail="The account with this id does not exist in the system.",
        )
    account = actions.account.update(session=session, model=account, data=data)
    return account


@router.get("/{account_id}", response_model=models.AccountRead)
def read_account(
    account_id: str,
    session: CommonSession,
    access: bool = Depends(rbac.RoleCheck(roles=[models.account.AccountRole.admin])),
) -> Any:
    """
    Get current account.
    """
    account = actions.account.get(session, id=account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail="The account with this id does not exist in the system.",
        )

    return account
