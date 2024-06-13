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

router = APIRouter()
CommonSession = Annotated[Session, Depends(deps.get_session)]


def get_full_user_profile(user: models.User) -> models.UserProfile:
    return {
        **user.account.dict(),
        "id": user.id,
        "profile": user.profile,
        "trainer": user.trainer,
        "student": user.student,
        "info": user.info,
    }


@router.get("/certificate", response_model=models.Document)
def get_certificate(
    *,
    session: CommonSession,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    cert = next((doc for doc in current_user.documents if doc.name == "certificate"), None)
    if cert is None:
        raise HTTPException(
            status_code=404, detail="Specified student's certificate could not be found"
        )
    return cert


@router.get("/", response_model=models.UserProfile)
def read_profile_me(
    session: CommonSession,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve profile containing full information on the account.
    """
    return get_full_user_profile(current_user)


@router.get("/{account_id}", response_model=models.UserProfile)
def read_profile(
    *,
    session: CommonSession,
    account_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> Any:
    """
    Get profile by ID.
    """
    account = actions.account.get(session, account_id)
    if current_user.type != models.user.UserType.admin and account.id != current_user.account.id:
        raise HTTPException(status_code=401, detail="Not authorized to view this profile")

    return get_full_user_profile(
        actions.user.get_by_all(session, workspace_id=workspace.id, account_id=account.id)
    )


@router.post("/", response_model=models.UserProfile, status_code=201)
def create_profile_me(
    *,
    session: CommonSession,
    data: models.ProfileCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
    response: Response,
) -> Any:
    """
    Create new profile.
    """
    # Check if profile already existed.
    profile = actions.profile.get_by_expressions(
        session, models.Profile.id == current_user.account_id
    )
    if profile:
        response.status_code = 200
        return actions.profile.update(session, model=profile, data=data)
    actions.profile.create(session=session, data=data, update={"id": current_user.account_id})
    return get_full_user_profile(current_user)


@router.put("/", response_model=models.UserProfile)
def update_profile_me(
    *,
    session: CommonSession,
    profile: Optional[models.ProfileUpdate],
    info: Optional[models.UserInfoUpdate],
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update an account's profile.
    """
    if profile:
        if current_user.profile is None:
            # actions.profile.create(session=session, data=profile)
            raise HTTPException(
                status_code=404,
                detail="Specified profile could not be found",
            )
        else:
            actions.profile.update(
                session=session,
                model=current_user.profile,
                data=profile,
                update={"id": current_user.profile.id},
            )

    if info:
        if current_user.info is None:
            # actions.info.create(session=session, data=info)
            # raise HTTPException(
            #     detail="Specified profile could not be found",
            # )
            # Do nothing for now.
            pass
        else:
            actions.info.update(session=session, model=current_user.info[0], data=info)

    session.refresh(current_user)
    return get_full_user_profile(current_user)


@router.put("/avatar", response_model=models.UserProfile)
def update_avatar(
    session: CommonSession,
    avatar: UploadFile,
    current_user: models.User = Depends(deps.get_current_active_user),
    workspace: models.Workspace = Depends(deps.get_current_workspace),
) -> Any:
    """
    Upload a new avatar for the account.
    """
    if current_user.profile is None:
        raise HTTPException(status_code=404, detail="Specified profile could not be found")
    storage_path = settings.STORAGE_PATH
    file_path = path.join(
        workspace.slug,
        "avatar",
        slugify(current_user.account.username) + path.splitext(avatar.filename)[1],
    )
    if not path.exists(path.join(storage_path, workspace.slug, "avatar")):
        makedirs(path.join(storage_path, workspace.slug, "avatar"), exist_ok=True)
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

    current_user.profile.avatar = path.join(settings.STORAGE_BASE_URL, file_path)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return get_full_user_profile(current_user)


@router.put("/{id}", response_model=models.UserProfile)
def update_profile(
    *,
    session: CommonSession,
    id: int,
    profile: Optional[models.ProfileUpdate],
    info: Optional[models.UserInfoUpdate],
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a account's profile.
    """
    current_profile = actions.profile.get(session=session, id=id)
    if not current_profile:
        raise HTTPException(status_code=404, detail="Specified profile could not be found")

    if (
        current_user.type != models.user.UserType.admin
        and current_profile.id != current_user.account.id
    ):
        raise HTTPException(
            status_code=400,
            detail="Not authorized to update profile for others",
        )
    if profile:
        actions.profile.update(session=session, model=current_profile, data=profile)

    if info:
        if current_user.info is None:
            # actions.info.create(session=session, data=info)
            # raise HTTPException(
            #     detail="Specified profile could not be found",
            # )
            # Do nothing for now.
            pass
        else:
            actions.info.update(session=session, model=current_user.info[0], data=info)

    return get_full_user_profile(current_user)
