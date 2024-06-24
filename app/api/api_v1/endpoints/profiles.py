import shutil
from os import makedirs, path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlmodel import Session
from typing_extensions import Annotated

from app import actions, models
from app.api import deps
from app.core.config import settings
from app.utils import slugify
from app.models import Account


router = APIRouter()
CommonSession = Annotated[Session, Depends(deps.get_session)]


@router.get("/", response_model=models.UserProfile)
def read_profile_me(
    # session: CommonSession,
    account: Account
) -> Any:
    """
    Retrieve profile containing full information on the account.
    """
    return account


@router.get("/{account_id}", response_model=models.UserProfile)
def read_profile(
    *,
    session: CommonSession,
    account_id: int,
    account: models.account = Depends(deps.get_current_account),
) -> Any:
    """
    Get profile by ID.
    """
    account = actions.account.get(session, account_id)
    if account.type != models.Account.UserType.admin and account.id != account.account.id:
        raise HTTPException(status_code=401, detail="Not authorized to view this profile")

    return account


@router.post("/", response_model=models.UserProfile, status_code=201)
def create_profile_me(
    *,
    session: CommonSession,
    data: models.ProfileCreate,
    account: models.Account = Depends(deps.get_current_account),
    response: Response,
) -> Any:
    """
    Create new profile.
    """
    # Check if profile already existed.
    profile = actions.profile.get_by_expressions(
        session, models.Profile.id == account.account_id
    )
    if profile:
        response.status_code = 200
        return actions.profile.update(session, model=profile, data=data)
    actions.profile.create(session=session, data=data, update={"id": account.account_id})
    return {"data": "Check"}


@router.put("/", response_model=models.UserProfile)
def update_profile_me(
    *,
    session: CommonSession,
    profile: Optional[models.ProfileUpdate],
    account: models.Account = Depends(deps.get_current_account),
) -> Any:
    """
    Update an account's profile.
    """
    if profile:
        if account.profile is None:
            # actions.profile.create(session=session, data=profile)
            raise HTTPException(
                status_code=404,
                detail="Specified profile could not be found",
            )
        else:
            account.profile.update(
                session=session,
                model=account.profile,
                data=profile,
                update={"id": account.profile.id},
            )

    session.refresh(account)
    return {"data": "Check"}


@router.put("/avatar", response_model=models.UserProfile)
def update_avatar(
    session: CommonSession,
    avatar: UploadFile,
    account: models.Account = Depends(deps.get_current_account),
) -> Any:
    """
    Upload a new avatar for the account.
    """
    if account.profile is None:
        raise HTTPException(status_code=404, detail="Specified profile could not be found")
    storage_path = settings.STORAGE_PATH
    file_path = path.join(
        "avatar",
        slugify(account.username) + path.splitext(avatar.filename)[1],
    )
    if not path.exists(path.join(storage_path, "avatar")):
        makedirs(path.join(storage_path, "avatar"), exist_ok=True)
    avfile = path.join(storage_path, file_path)

    try:
        with open(avfile, "wb") as f:
            shutil.copyfileobj(avatar.file, f)

    except Exception as err:
        raise HTTPException(
            detail=f"{err} encountered while uploading {avatar.filename}", status_code=500
        )
    finally:
        avatar.file.close()

    account.profile.avatar = path.join(settings.STORAGE_BASE_URL, file_path)
    session.add(account)
    session.commit()
    session.refresh(account)

    return {"message": "Check"}


@router.put("/{id}", response_model=models.UserProfile)
def update_profile(
    *,
    session: CommonSession,
    id: int,
    profile: Optional[models.ProfileUpdate],
    account: models.account = Depends(deps.get_current_account),
) -> Any:
    """
    Update a account's profile.
    """
    current_profile = actions.profile.get(session=session, id=id)
    if not current_profile:
        raise HTTPException(status_code=404, detail="Specified profile could not be found")

    if (
        account.type != models.user.UserType.admin
        and current_profile.id != account.account.id
    ):
        raise HTTPException(
            status_code=400,
            detail="Not authorized to update profile for others",
        )
    if profile:
        actions.profile.update(session=session, model=current_profile, data=profile)

    # if info:
    #     if account.info is None:
    #         # actions.info.create(session=session, data=info)
    #         # raise HTTPException(
    #         #     detail="Specified profile could not be found",
    #         # )
    #         # Do nothing for now.
    #         pass
    #     else:
    #         actions.info.update(session=session, model=account.info[0], data=info)

    return {"message": "check this"}
