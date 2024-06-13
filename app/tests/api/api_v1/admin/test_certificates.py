from os import remove
from os.path import join, splitext
from random import randrange

from faker import Faker
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import Document
from app.models.user import UserType
from app.tests.utils.user import (
    create_random_fulluser,
    create_random_fulluser_with_token,
    create_random_user,
    create_random_user_with_token,
)
from app.tests.utils.workspace import (
    create_random_workspace,
    create_random_workspace_and_account,
    create_random_workspace_and_account_with_token,
)
from app.utils import slugify


def test_upload_certificate(
    client: TestClient, session: Session, faker: Faker, superuser_account_token_headers
) -> None:
    workspace, _, header = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    user = create_random_fulluser(
        session,
        workspace,
        type=UserType.learner,
    )
    file_content = faker.text()
    fname = faker.file_name(extension="txt")
    fpath = join("./tmp", fname)
    with open(fpath, "w") as f:
        f.write(file_content)

    with open(fpath, "rb") as f:
        response = client.post(
            f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
            files={"certificate": (fname, f, "image/jpeg")},
            headers=header,
        )
    assert response.status_code == 201
    userdict = response.json()
    assert userdict["id"] == user.id

    session.refresh(user)
    cert = user.documents[-1].dict()
    assert cert["url"] == join(
        settings.STORAGE_BASE_URL,
        workspace.slug,
        "certificate",
        f"{slugify(user.account.username)}{splitext(fpath)[1]}",
    )

    response1 = client.get(cert["url"])
    assert response1.status_code == 200
    assert response1.content.decode("utf-8") == file_content

    # Cleanup files.
    remove(fpath)
    remove(cert["url"].replace(settings.STORAGE_BASE_URL, settings.STORAGE_PATH))


def test_upload_certificate_unauthorized(
    client: TestClient,
    session: Session,
    faker: Faker,
) -> None:
    workspace, _ = create_random_workspace_and_account(session)
    user, headers = create_random_user_with_token(client, session, workspace)
    response = client.post(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        files={"certificate": (None, None, "image/jpeg")},
        headers=headers,
    )

    # @todo why is this 400? Should be 401
    assert response.status_code == 400


def test_upload_certificate_non_existent(
    client: TestClient, session: Session, faker: Faker
) -> None:
    file_content = faker.text()
    fname = faker.file_name(extension="txt")
    fpath = join("./tmp", fname)
    with open(fpath, "w") as f:
        f.write(file_content)

    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    with open(fpath, "rb") as f:
        response = client.post(
            f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/1",
            files={"certificate": (fname, f, "image/jpeg")},
            headers=headers,
        )
    assert response.status_code == 404

    user, _ = create_random_user_with_token(client, session, workspace)
    with open(fpath, "rb") as f:
        response = client.post(
            f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
            files={"certificate": (fname, f, "image/jpeg")},
            headers=headers,
        )
    assert response.status_code == 404


def test_get_certificate(client: TestClient, session: Session, faker: Faker) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    user = create_random_fulluser(
        session,
        workspace,
        type=UserType.learner,
    )
    test_url = faker.uri()
    user.documents.append(
        Document(
            name="certificate",
            url=test_url,
            user_id=user.id,
            document_type="certificate",
        )
    )
    session.add(user)
    session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    assert response.status_code == 200
    cert = response.json()
    assert cert["name"] == "certificate"
    assert cert["url"] == test_url


def test_get_certificate_unauthorized(
    client: TestClient,
    session: Session,
    faker: Faker,
) -> None:
    workspace, _ = create_random_workspace_and_account(session)
    user, headers = create_random_fulluser_with_token(
        client,
        session,
        workspace,
        type=UserType.learner,
    )
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    # @todo why is this 401, while the one above
    # (test_upload_certificate_unauthorized) is 400?
    assert response.status_code == 401


def test_get_certificate_non_existent(client: TestClient, session: Session, faker: Faker) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/1",
        headers=headers,
    )
    assert response.status_code == 404

    user = create_random_user(session, workspace)
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    assert response.status_code == 404


def test_get_certificate_other_workspace(
    client: TestClient, session: Session, faker: Faker
) -> None:
    workspace, account, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    workspace1 = create_random_workspace(session, account, type=UserType.admin)
    user = create_random_fulluser(
        session,
        workspace,
        type=UserType.learner,
    )
    test_url = faker.uri()
    user.documents.append(
        Document(
            name="certificate",
            url=test_url,
            user_id=user.id,
            document_type="certificate",
        )
    )
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificates",
        headers=headers,
    )
    assert response.status_code == 200
    certs = response.json()
    assert certs[0] == Document.from_orm(user.documents[0]).jsond()

    response = client.get(
        f"{settings.API_V1_STR}/{workspace1.slug}/admin/profiles/certificates",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


def test_delete_certificate(client: TestClient, session: Session, faker: Faker) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    user = create_random_fulluser(
        session,
        workspace,
        type=UserType.learner,
    )
    test_url = faker.uri()
    user.documents.append(
        Document(
            name="certificate",
            url=test_url,
            user_id=user.id,
            document_type="certificate",
        )
    )
    session.add(user)
    session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    assert response.status_code == 200
    cert = response.json()
    assert cert["name"] == "certificate"
    assert cert["url"] == test_url
    assert len(user.documents) == 1

    response = client.delete(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    assert response.status_code == 200
    assert len(user.documents) == 0


def test_delete_certificate_unauthorized(
    client: TestClient,
    session: Session,
    faker: Faker,
) -> None:
    workspace, _ = create_random_workspace_and_account(session)
    user, headers = create_random_fulluser_with_token(
        client,
        session,
        workspace,
        type=UserType.learner,
    )
    response = client.delete(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    assert response.status_code == 401


def test_delete_certificate_non_existent(
    client: TestClient, session: Session, faker: Faker
) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    response = client.delete(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/1",
        headers=headers,
    )
    assert response.status_code == 404

    user = create_random_user(session, workspace)
    response = client.delete(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificate/{user.id}",
        headers=headers,
    )
    assert response.status_code == 404


def test_get_multiple_certificates(client: TestClient, session: Session, faker: Faker) -> None:
    workspace, _, headers = create_random_workspace_and_account_with_token(
        client, session, type=UserType.admin
    )
    users = []
    certs = []
    for _ in range(randrange(3, 10)):
        user = create_random_fulluser(session, workspace, type=UserType.learner)
        users.append(user)
        cert = Document(
            name="certificate",
            document_type="certificate",
            owner_id=user.id,
            url=faker.url(),
        )
        user.documents.append(cert)
        session.add(cert)
        session.commit()
        certs.append(Document.from_orm(cert).jsond())
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificates",
        headers=headers,
    )
    assert response.status_code == 200
    certs_json = response.json()
    assert certs_json == certs


def test_get_certificates_unauthorized(
    client: TestClient,
    session: Session,
    faker: Faker,
) -> None:
    workspace, _ = create_random_workspace_and_account(session)
    _, headers = create_random_user_with_token(
        client,
        session,
        workspace,
        type=UserType.learner,
    )
    response = client.get(
        f"{settings.API_V1_STR}/{workspace.slug}/admin/profiles/certificates",
        headers=headers,
    )
    assert response.status_code == 401
