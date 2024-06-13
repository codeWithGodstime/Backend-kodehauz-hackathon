import random

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import actions, models
from app.core.config import settings
from app.models.account import AccountRead, AccountRole
from app.tests.utils.account import create_random_account
from app.tests.utils.category import create_random_categories
from app.tests.utils.user import random_user_create_full
from app.tests.utils.workspace import create_random_workspace, create_random_workspace_and_account

usertypes = {
    "learner": models.user.UserType.learner,
    "trainer": models.user.UserType.trainer,
}


@pytest.mark.parametrize("usertype", usertypes.values(), ids=usertypes.keys())
def test_user_register_open_allowed(
    client: TestClient, session: Session, usertype: models.user.UserType
) -> None:
    workspace, _ = create_random_workspace_and_account(
        session, workspace_status=WorkspaceStatus.open
    )
    level, track, stage = create_random_categories(session, workspace)
    data = random_user_create_full(
        workspace,
        type=usertype,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
    )
    data.account.email = data.account.email.upper()
    settings.USERS_OPEN_REGISTRATION = True
    response = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert response.status_code == 201

    user = actions.user.get_by_email(
        session=session, email=data.account.email.lower(), workspace_id=workspace.id
    )
    json_account = response.json()
    assert user
    assert user.status == UserStatus.active
    assert user.type == usertype
    assert json_account == models.AccountRead.from_orm(user.account).jsond()
    assert user.account.username == data.account.username
    assert user.account.email == data.account.email.lower()  # check case sensitivity
    assert user.account.current_workspace_id == workspace.id

    profile = session.get(models.Profile, user.account.id)
    assert profile
    assert profile.first_name == data.profile.first_name
    assert profile.last_name == data.profile.last_name

    if usertype == models.user.UserType.learner:
        student = session.get(models.Student, user.id)
        assert student
        assert student.id == user.id
        assert student.track_id == data.student.track_id
        assert student.level_id == data.student.level_id
        assert student.stage_id == data.student.stage_id

    if usertype == models.user.UserType.trainer:
        trainer = session.get(models.Trainer, user.id)
        assert trainer
        assert trainer.id == user.id
        assert trainer.track_id == data.trainer.track_id
        assert trainer.level_id == data.trainer.level_id

    userinfo = session.get(models.UserInfo, user.id)
    assert userinfo
    assert userinfo.id == user.id
    assert userinfo.qualification == data.info.qualification
    assert userinfo.employment_status == data.info.employment_status
    assert userinfo.information_source == data.info.information_source
    assert userinfo.survey_data == data.info.survey_data


def test_user_register_open_not_allowed(
    client: TestClient,
    session: Session,
) -> None:
    workspace, _ = create_random_workspace_and_account(
        session, workspace_status=WorkspaceStatus.open
    )
    data = random_user_create_full(workspace)
    settings.USERS_OPEN_REGISTRATION = False
    response = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Open account registration is forbidden on this server"


fields = ["email", "username", "phone"]


@pytest.mark.parametrize("fieldname", fields, ids=fields)
def test_user_register_open_existing(
    client: TestClient,
    session: Session,
    fieldname: str,
) -> None:
    workspace, account = create_random_workspace_and_account(
        session, workspace_status=WorkspaceStatus.open
    )
    args = {fieldname: getattr(account, fieldname)}
    level, track, stage = create_random_categories(session, workspace)
    data = random_user_create_full(
        workspace,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
        **args,
    )
    settings.USERS_OPEN_REGISTRATION = True
    response = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert response.status_code == 400
    content = response.json()
    assert (
        content["detail"]
        == "An account with this username, phone or email already exists in the system"
    )


categories = [
    "level-learner",
    "track-learner",
    "stage-learner",
    "level-trainer",
    "track-trainer",
]
parameters = [
    ["level", UserType.learner],
    ["track", UserType.learner],
    ["stage", UserType.learner],
    ["level", UserType.trainer],
    ["track", UserType.trainer],
]


@pytest.mark.parametrize("category,usertype", parameters, ids=categories)
def test_user_register_open_invalid_categories(
    client: TestClient,
    session: Session,
    category: str,
    usertype: str,
) -> None:
    workspace, account = create_random_workspace_and_account(
        session, workspace_status=WorkspaceStatus.open
    )
    level, track, stage = create_random_categories(session, workspace)
    data = random_user_create_full(
        workspace,
        type=usertype,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
    )
    # Change the ids to invalid values.
    id = random.randint(100, 500)
    attr = getattr(data, "student") if usertype == UserType.learner else getattr(data, "trainer")
    setattr(attr, f"{category}_id", id)
    settings.USERS_OPEN_REGISTRATION = True
    response = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == f"Could not create account, {category} with ID {id} not found"


@pytest.mark.parametrize("usertype", usertypes.values(), ids=usertypes.keys())
def test_user_register_open_invalid_categories_in_diff_workspaces(
    client: TestClient,
    session: Session,
    usertype: str,
) -> None:
    settings.USERS_OPEN_REGISTRATION = True
    workspace1, _ = create_random_workspace_and_account(
        session, workspace_status=WorkspaceStatus.open
    )
    workspace2, _ = create_random_workspace_and_account(
        session, workspace_status=WorkspaceStatus.open
    )
    level1, track1, stage1 = create_random_categories(session, workspace1)
    level2, track2, stage2 = create_random_categories(session, workspace2)
    data = random_user_create_full(
        workspace1,
        type=usertype,
        level_id=level2.id,
        track_id=track1.id,
        stage_id=stage1.id,
    )
    r = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert r.status_code == 404
    assert r.json()["detail"] == f"Could not create account, level with ID {level2.id} not found"

    data = random_user_create_full(
        workspace1,
        type=usertype,
        level_id=level1.id,
        track_id=track2.id,
        stage_id=stage1.id,
    )
    r = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert r.status_code == 404
    assert r.json()["detail"] == f"Could not create account, track with ID {track2.id} not found"

    if usertype == "learner":
        data = random_user_create_full(
            workspace1,
            type=usertype,
            level_id=level1.id,
            track_id=track1.id,
            stage_id=stage2.id,
        )
        r = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
        assert r.status_code == 404
        assert (
            r.json()["detail"] == f"Could not create account, stage with ID {stage2.id} not found"
        )


@pytest.mark.parametrize("usertype", usertypes.values(), ids=usertypes.keys())
def test_user_register_open_unavailable_workspaces(
    client: TestClient,
    session: Session,
    usertype: str,
) -> None:
    # Restricted workspaces should fail to register.
    settings.USERS_OPEN_REGISTRATION = True
    account = create_random_account(session, role=AccountRole.admin)
    for status in [WorkspaceStatus.locked, WorkspaceStatus.readonly, WorkspaceStatus.restricted]:
        workspace = create_random_workspace(session, account, workspace_status=status)
        level, track, stage = create_random_categories(session, workspace)
        data = random_user_create_full(
            workspace,
            type=usertype,
            level_id=level.id,
            track_id=track.id,
            stage_id=stage.id,
        )
        r = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
        assert r.status_code == 404
        assert r.json()["detail"] == "No open workspace found with the specified name"

    # Open workspace should succeed in registering.
    workspace = create_random_workspace(session, account, workspace_status=WorkspaceStatus.open)
    level, track, stage = create_random_categories(session, workspace)
    data = random_user_create_full(
        workspace,
        type=usertype,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
    )
    r = client.post(f"{settings.API_V1_STR}/open", json=data.jsond())
    assert r.status_code == 201
    new_account = actions.account.get_by_email(session, email=data.account.email)
    assert r.json() == AccountRead.from_orm(new_account).jsond()
