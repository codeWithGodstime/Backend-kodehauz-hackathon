import random
from typing import List

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import actions, models
from app.core.config import settings
from app.models.account import AccountReadAdmin
from app.models.profile import ProfileRead
from app.models.student import StudentRead, UserInfoRead, UserStudentSubmission
from app.models.submission import SubmissionStatus
from app.models.user import User, UserType
from app.tests.utils.category import create_random_categories, create_random_category
from app.tests.utils.request import read_stream_events
from app.tests.utils.task import create_random_submissions, create_random_tasks, random_task_create
from app.tests.utils.user import create_random_fulluser
from app.tests.utils.workspace import (
    create_random_workspace,
    create_random_workspace_and_account_with_token,
)


def test_get_promotion_users(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    level, track, stage = create_random_categories(session, workspace)
    trainer = create_random_fulluser(
        session,
        workspace,
        type=UserType.trainer,
        level_id=level.id,
        track_id=track.id,
    )
    learners = []
    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=stage.id,
            )
        )
    tasks = create_random_tasks(
        session,
        workspace,
        10,
        owner_id=trainer.id,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
        points=100,
    )
    # Another level, track, stage set
    _, _, stage1 = create_random_categories(session, workspace)
    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=stage1.id,
            )
        )
    tasks1 = create_random_tasks(
        session,
        workspace,
        10,
        owner_id=trainer.id,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage1.id,
        points=100,
    )
    assert actions.submission.get_multi(session) == []
    submissions: List[models.Submission] = []
    for learner in learners:
        up = random.randint(4, len(tasks))
        dn = random.randint(0, up)
        submissions += create_random_submissions(
            session,
            tasks=tasks[dn:up],
            user=learner,
        )
        submissions += create_random_submissions(
            session,
            tasks=tasks1[dn:up],
            user=learner,
        )

    cutoff = 75
    students = {}
    successful = set()
    succ_tasks = set()
    for sub in submissions:
        if sub.status == SubmissionStatus.graded:
            sub.score = random.randint(50, 100)
            session.add(sub)
            if sub.score >= cutoff and sub.task.stage_id == sub.student.student.stage_id:
                successful.add(sub.student_id)
                students[sub.student_id] = sub.student
                succ_tasks.add(sub.task_id)

    session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/promotion",
        headers=headers,
        params={"limit": 1000, "cutoff": 75},
    )
    assert response.status_code == 200
    json = response.json()
    # assert len(users_json) == len(successful)
    successful_users = set(map(lambda x: x["id"], json["students"]))
    assert successful_users == successful
    for json_user in json["students"]:
        user: User = students[json_user["id"]]
        assert json_user["account"] == AccountReadAdmin.from_orm(user.account).jsond()
        assert json_user["profile"] == ProfileRead.from_orm(user.account.profile).jsond()
        assert json_user["student"] == StudentRead.from_orm(user.student).jsond()
        assert json_user["info"] == UserInfoRead.from_orm(user.info).jsond()
    successful_tasks = set(map(lambda x: x["id"], json["tasks"]))
    assert successful_tasks == succ_tasks


def test_get_promoted_users_unauthorized(
    client: TestClient,
    session: Session,
) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(client, session)
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/promotion",
        headers=headers,
        params={"limit": 1000, "cutoff": 75},
    )
    assert response.status_code == 401


def test_post_promoted_users(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    level, track, stage = create_random_categories(session, workspace)
    stage.order = 0
    session.add(stage)
    trainer = create_random_fulluser(
        session,
        workspace,
        type=UserType.trainer,
        level_id=level.id,
        track_id=track.id,
    )
    learners: List[models.User] = []
    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=stage.id,
            )
        )
    # Create additional stages, learners and tasks.
    stages = [stage]
    stage_k = {stage.id: stage}
    stage_o = {stage.order: stage}
    for i in range(random.randint(2, 6)):
        stage_x = create_random_category(session, models.Stage, workspace, order=i + 1)
        stages.append(stage_x)
        stage_k[stage_x.id] = stage_x
        stage_o[stage_x.order] = stage_x

    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=stages[random.randrange(0, len(stages))].id,
            )
        )
    tasks: List[models.Task] = []
    for _ in range(random.randint(6, 10)):
        tasks.append(
            actions.task.create(
                session,
                workspace,
                data=random_task_create(
                    owner_id=trainer.id,
                    level_id=level.id,
                    track_id=track.id,
                    stage_id=stages[random.randrange(0, len(stages))].id,
                    points=100,
                ),
            )
        )

    submissions: List[models.Submission] = []
    previous_stages = {}
    for learner in learners:
        own_tasks = [task for task in tasks if task.stage.order <= learner.student.stage.order]
        submissions += create_random_submissions(
            session,
            tasks=own_tasks,
            user=learner,
        )
        previous_stages[learner.id] = learner.student.stage_id

    cutoff = 75
    promoted = {}
    promo_stages = list(stage_k.keys())[0:-2]
    for sub in submissions:
        if sub.status == SubmissionStatus.graded:
            sub.score = random.randint(50, 100)
            session.add(sub)
            if (
                sub.score >= cutoff
                and sub.task.stage_id == sub.student.student.stage_id
                and sub.task.stage_id in promo_stages
            ):
                promoted[sub.student_id] = (sub.task.stage_id, stage_o[sub.task.stage.order + 1].id)

    session.commit()

    data = {
        "level_ids": [level.id],
        "track_ids": [track.id],
        "stage_ids": promo_stages,
        "cutoff": cutoff,
    }
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/promotion",
        headers=headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "Promotion successfully completed"

    for learner in learners:
        session.refresh(learner.student)
        if learner.student.id in promoted.keys():
            # Compare with expected new stage.
            assert learner.student.stage_id == promoted[learner.student.id][1]
            # New stage and old stage should not be the same.
            assert promoted[learner.student.id][0] != promoted[learner.student.id][1]
        else:
            assert learner.student.stage_id == previous_stages[learner.student.id]

    events = read_stream_events(
        client, f"{settings.API_V1_STR}/{workspace.slug}/stream", timeout=1, iterations=1
    )
    assert len(events) == 1
    assert events[0]["data"]["name"] == "promotion"
    assert sorted(events[0]["data"]["affectedIds"]) == sorted(list(promoted.keys()))


def test_post_promoted_users_non_existent_stage(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, account, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    level, track, stage = create_random_categories(session, workspace)
    stage.order = 0
    session.add(stage)
    trainer = create_random_fulluser(
        session,
        workspace,
        type=UserType.trainer,
        level_id=level.id,
        track_id=track.id,
    )
    learners: List[models.User] = []
    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=stage.id,
            )
        )
    # Create additional stage in another workspace.
    workspace1 = create_random_workspace(session, account)
    create_random_category(session, models.Stage, workspace1, order=0)
    create_random_category(session, models.Stage, workspace1, order=1)

    tasks: List[models.Task] = []
    for _ in range(random.randint(6, 10)):
        tasks.append(
            actions.task.create(
                session,
                workspace,
                data=random_task_create(
                    owner_id=trainer.id,
                    level_id=level.id,
                    track_id=track.id,
                    stage_id=stage.id,
                    points=100,
                ),
            )
        )

    submissions: List[models.Submission] = []
    previous_stages = {}
    for learner in learners:
        submissions += create_random_submissions(
            session, tasks=tasks, user=learner, status=SubmissionStatus.graded, score=90
        )
        previous_stages[learner.id] = learner.student.stage_id

    promo_stages = [stage.id]

    session.commit()

    data = {
        "level_ids": [level.id],
        "track_ids": [track.id],
        "stage_ids": promo_stages,
        "cutoff": 75,
    }
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/promotion",
        headers=headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "Promotion successfully completed"
    for learner in learners:
        session.refresh(learner.student)
        assert learner.student.stage_id == previous_stages[learner.id]


def test_post_promoted_users_unauthorized(
    client: TestClient,
    session: Session,
) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(client, session)
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/promotion",
        headers=headers,
        json={
            "level_ids": [1],
            "track_ids": [1],
            "stage_ids": [1],
            "cutoff": 75,
        },
    )
    assert response.status_code == 401


def test_get_demotion_users(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    level, track, stage = create_random_categories(session, workspace)
    level1, track1, stage1 = create_random_categories(session, workspace)
    stage.order = 0
    stage1.order = 1
    session.add(stage)
    session.add(stage1)
    session.commit()
    trainer = create_random_fulluser(
        session,
        workspace,
        type=UserType.trainer,
        level_id=level.id,
        track_id=track.id,
    )
    learners: List[models.User] = []
    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=random.choice([stage.id, stage1.id]),
            )
        )
    tasks = create_random_tasks(
        session,
        workspace,
        10,
        owner_id=trainer.id,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
        points=100,
    )
    submissions: List[models.Submission] = []
    previous_stages = {}
    for learner in learners:
        own_tasks = [task for task in tasks if task.stage.order <= learner.student.stage.order]
        submissions += create_random_submissions(
            session,
            tasks=own_tasks,
            user=learner,
        )
        previous_stages[learner.id] = learner.student.stage_id

    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/demotion",
        headers=headers,
    )
    assert response.status_code == 200
    demo_json = response.json()

    for_demo = [UserStudentSubmission.from_orm(user).jsond() for user in learners]

    assert demo_json["students"] == for_demo


def test_get_demoted_users_unauthorized(
    client: TestClient,
    session: Session,
) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(client, session)
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/demotion",
        headers=headers,
        params={"limit": 1000},
    )
    assert response.status_code == 401


def test_post_demoted_users(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    level, track, stage = create_random_categories(session, workspace)
    level1, track1, stage1 = create_random_categories(session, workspace)
    stage.order = 0
    stage1.order = 1
    level.order = 0
    level1.order = 1
    session.add(stage)
    session.add(stage1)
    session.add(level)
    session.add(level1)
    session.commit()
    learners: List[models.User] = []
    affected: List[int] = []
    old_states = {}
    for _ in range(random.randint(9, 10)):
        learner = create_random_fulluser(
            session,
            workspace,
            type=UserType.learner,
            level_id=random.choice([level.id, level1.id]),
            track_id=track.id,
            stage_id=random.choice([stage.id, stage1.id]),
        )
        old_states[learner.id] = (
            learner.student.level_id,
            learner.student.track_id,
            learner.student.stage_id,
        )
        learners.append(learner)
        if (
            learner.student.stage_id == stage.id
            and learner.student.track_id == track.id
            and learner.student.level_id == level1.id
        ):
            affected.append(learner.id)
    data = {
        "level_from": level1.id,
        "track_from": track.id,
        "stage_from": stage.id,
        "level_to": level.id,
        "track_to": track1.id,
        "stage_to": stage1.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/demotion",
        headers=headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "Demotion successfully completed"

    for learner in learners:
        if old_states[learner.id] == (level1.id, track.id, stage.id):
            assert learner.student.stage_id == stage1.id
            assert learner.student.level_id == level.id
            assert learner.student.track_id == track1.id
        else:
            assert (
                learner.student.level_id,
                learner.student.track_id,
                learner.student.stage_id,
            ) == old_states[learner.id]

    events = read_stream_events(
        client, f"{settings.API_V1_STR}/{workspace.slug}/stream", timeout=1, iterations=1
    )
    assert len(events) == 1
    assert events[0]["data"]["name"] == "demotion"
    assert events[0]["data"]["affectedIds"] == affected


def test_post_demoted_users_unauthorized(
    client: TestClient,
    session: Session,
) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(client, session)
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/demotion",
        headers=headers,
        json={
            "level_ids": 1,
            "stage_ids": 1,
        },
    )
    assert response.status_code == 401


def test_get_demotion_users_other_workspace(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, account, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    workspace1 = create_random_workspace(session, account, type=UserType.admin)
    level, track, stage = create_random_categories(session, workspace)
    level1, track1, stage1 = create_random_categories(session, workspace)
    stage.order = 0
    stage1.order = 1
    session.add(stage)
    session.add(stage1)
    session.commit()
    trainer = create_random_fulluser(
        session,
        workspace,
        type=UserType.trainer,
        level_id=level.id,
        track_id=track.id,
    )
    learners: List[models.User] = []
    for _ in range(random.randint(5, 10)):
        learners.append(
            create_random_fulluser(
                session,
                workspace,
                type=UserType.learner,
                level_id=level.id,
                track_id=track.id,
                stage_id=random.choice([stage.id, stage1.id]),
            )
        )
    tasks = create_random_tasks(
        session,
        workspace,
        10,
        owner_id=trainer.id,
        level_id=level.id,
        track_id=track.id,
        stage_id=stage.id,
        points=100,
    )
    submissions: List[models.Submission] = []
    previous_stages = {}
    for learner in learners:
        own_tasks = [task for task in tasks if task.stage.order <= learner.student.stage.order]
        submissions += create_random_submissions(
            session,
            tasks=own_tasks,
            user=learner,
        )
        previous_stages[learner.id] = learner.student.stage_id

    response = client.get(
        f"{settings.API_V1_STR}/{workspace1.slug}/admin/tasks/demotion",
        headers=headers,
    )
    assert response.status_code == 200
    demo_json = response.json()

    assert demo_json["students"] == []


def test_post_demoted_users_selected(
    client: TestClient,
    session: Session,
) -> None:
    # Create tasks and submissions for a set of level, track, stage
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    level, track, stage = create_random_categories(session, workspace)
    level1, track1, stage1 = create_random_categories(session, workspace)
    learners: List[models.User] = []
    affected: List[int] = []
    old_states = {}
    selected = []
    for _ in range(random.randint(9, 10)):
        learner = create_random_fulluser(
            session,
            workspace,
            type=UserType.learner,
            level_id=random.choice([level.id, level1.id]),
            track_id=track.id,
            stage_id=random.choice([stage.id, stage1.id]),
        )
        old_states[learner.id] = (
            learner.student.level_id,
            learner.student.track_id,
            learner.student.stage_id,
        )
        if random.randint(0, 10) > 5:
            selected.append(learner.id)
        learners.append(learner)
        if (
            learner.student.stage_id == stage.id
            and learner.student.track_id == track.id
            and learner.student.level_id == level1.id
            and learner.student.id in selected
        ):
            affected.append(learner.id)
    data = {
        "level_from": level1.id,
        "track_from": track.id,
        "stage_from": stage.id,
        "level_to": level.id,
        "track_to": track1.id,
        "stage_to": stage1.id,
        "student_ids": selected,
    }
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/tasks/demotion",
        headers=headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "Demotion successfully completed"

    for learner in learners:
        if old_states[learner.id] == (level1.id, track.id, stage.id) and learner.id in selected:
            assert learner.student.stage_id == stage1.id
            assert learner.student.level_id == level.id
            assert learner.student.track_id == track1.id
        else:
            assert (
                learner.student.level_id,
                learner.student.track_id,
                learner.student.stage_id,
            ) == old_states[learner.id]

    events = read_stream_events(
        client, f"{settings.API_V1_STR}/{workspace.slug}/stream", timeout=1, iterations=1
    )
    assert len(events) == 1
    assert events[0]["data"]["name"] == "demotion"
    assert events[0]["data"]["affectedIds"] == affected
