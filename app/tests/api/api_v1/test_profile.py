# from os import makedirs, remove
# from os.path import join, splitext

# from faker import Faker
# from fastapi.testclient import TestClient
# from sqlmodel import Session

# from app.core.config import settings
# from app.models.account import AccountRole
# from app.models.profile import ProfileUpdate
# from app.models.user import UserType
# from app.tests.utils.profile import create_random_profile
# from app.utils import slugify


# def test_read_my_profile(client: TestClient, session: Session) -> None:
#     _, account, headers = create_random_workspace_and_account_with_token(
#         client,
#         session,
#         role=AccountRole.admin,
#     )
#     workspace = create_random_workspace(session, account)
#     profile = create_random_profile(session, account)
#     response = client.get(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles",
#         headers=headers,
#     )
#     assert response.status_code == 200
#     content = response.json()["profile"]
#     assert content["first_name"] == profile.first_name
#     assert content["last_name"] == profile.last_name
#     assert content["gender"] == profile.gender.value
#     assert content["date_of_birth"] == str(profile.date_of_birth)
#     assert content["marital_status"] == profile.marital_status.value
#     assert content["id"] == profile.id

#     user_json = response.json()
#     assert user_json["id"] == account.users[1].id


# def test_read_profile_superuser(client: TestClient, session: Session) -> None:
#     workspace, _, headers = create_random_workspace_and_account_with_token(
#         client,
#         session,
#         role=AccountRole.admin,
#         type=UserType.admin,
#     )
#     user = create_random_user(session, workspace)
#     profile = create_random_profile(session, user.account)
#     response = client.get(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles/{profile.id}",
#         headers=headers,
#     )
#     assert profile.id == user.account.id
#     assert response.status_code == 200
#     content = response.json()["profile"]
#     assert content["first_name"] == profile.first_name
#     assert content["last_name"] == profile.last_name
#     assert content["id"] == profile.id


# def test_read_profile(client: TestClient, session: Session) -> None:
#     workspace, account, headers = create_random_workspace_and_account_with_token(
#         client, session, role=AccountRole.admin
#     )
#     profile = create_random_profile(session, account)
#     response = client.get(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles/{profile.id}",
#         headers=headers,
#     )
#     assert response.status_code == 200
#     content = response.json()["profile"]
#     assert content["id"] == profile.id


# def test_read_profile_not_permitted(client: TestClient, session: Session) -> None:
#     workspace, account = create_random_workspace_and_account(session, role=AccountRole.admin)
#     profile = create_random_profile(session, account)
#     _, headers = create_random_user_with_token(client, session, workspace)
#     response = client.get(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles/{profile.id}",
#         headers=headers,
#     )
#     assert response.status_code == 401


# # def test_create_profile_different_user(client: TestClient, session: Session) -> None:
# #     workspace, account, headers = create_random_workspace_and_account_with_token(
# #         client, session, role=AccountRole.admin
# #     )
# #     data = random_profile_create(id=account.id)
# #     response = client.post(
# #         f"{settings.API_V1_STR}/{workspace.slug}/profiles",
# #         headers=headers,
# #         json=data.jsond(),
# #     )
# #     assert response.status_code == 400


# def test_update_my_profile(client: TestClient, session: Session, faker: Faker) -> None:
#     workspace, account, headers = create_random_workspace_and_account_with_token(
#         client, session, role=AccountRole.admin
#     )
#     profile = create_random_profile(session, account)
#     profile_update = ProfileUpdate(
#         id=account.id,
#         first_name=faker.name(),
#         last_name=faker.name(),
#     )
#     data = {"profile": profile_update.jsond(), "info": {"survey_data": {}}}
#     assert profile.first_name != profile_update.first_name
#     assert profile.last_name != profile_update.last_name
#     response = client.put(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles",
#         json=data,
#         headers=headers,
#     )
#     assert response.status_code == 200
#     content = response.json()
#     assert content["profile"]["first_name"] == profile_update.first_name
#     assert content["profile"]["last_name"] == profile_update.last_name
#     assert content["profile"]["id"] == profile.id

#     session.refresh(profile)
#     assert profile.first_name == profile_update.first_name
#     assert profile.last_name == profile_update.last_name


# def test_update_profile_not_found(client: TestClient, session: Session, faker: Faker) -> None:
#     workspace, account, headers = create_random_workspace_and_account_with_token(
#         client, session, role=AccountRole.admin
#     )
#     data = {
#         "profile": ProfileUpdate().jsond(),
#         "info": {"survey_data": {}},
#     }
#     response = client.put(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles/100000",
#         json=data,
#         headers=headers,
#     )
#     assert response.status_code == 404


# def test_update_profile_not_permitted(
#     client: TestClient,
#     session: Session,
# ) -> None:
#     workspace, account = create_random_workspace_and_account(session, role=AccountRole.admin)
#     profile = create_random_profile(session, account)
#     _, headers = create_random_user_with_token(client, session, workspace)
#     data = {
#         "profile": ProfileUpdate().jsond(),
#         "info": {"survey_data": {}},
#     }
#     response = client.put(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles/{profile.id}",
#         json=data,
#         headers=headers,
#     )
#     assert response.status_code == 400


# def test_update_profile(client: TestClient, session: Session, faker: Faker) -> None:
#     workspace, account, headers = create_random_workspace_and_account_with_token(
#         client, session, role=AccountRole.admin
#     )
#     profile = create_random_profile(session, account)
#     profile_data = ProfileUpdate(
#         first_name=faker.name(),
#         last_name=faker.name(),
#     )
#     data = {
#         "profile": profile_data.jsond(),
#         "info": {"survey_data": {}},
#     }
#     assert profile.first_name != profile_data.first_name
#     assert profile.last_name != profile_data.last_name
#     response = client.put(
#         f"{settings.API_V1_STR}/{workspace.slug}/profiles/{profile.id}",
#         json=data,
#         headers=headers,
#     )
#     assert response.status_code == 200
#     content = response.json()["profile"]
#     assert content["first_name"] == profile_data.first_name
#     assert content["last_name"] == profile_data.last_name

#     session.refresh(profile)
#     assert profile.first_name == profile_data.first_name
#     assert profile.last_name == profile_data.last_name


# def test_update_profile_avatar(client: TestClient, session: Session, faker: Faker) -> None:
#     workspace, account, headers = create_random_workspace_and_account_with_token(
#         client, session, role=AccountRole.admin
#     )
#     profile = create_random_profile(session, account)
#     file_content = faker.text()
#     fname = faker.file_name(extension="txt")
#     fpath = join("./tmp", fname)
#     makedirs("./tmp", exist_ok=True)
#     with open(fpath, "w") as f:
#         f.write(file_content)

#     with open(fpath, "rb") as f:
#         response = client.put(
#             f"{settings.API_V1_STR}/{workspace.slug}/profiles/avatar",
#             files={"avatar": (fname, f, "image/jpeg")},
#             headers=headers,
#         )
#     assert response.status_code == 200
#     profile = response.json()
#     assert profile["profile"]["avatar"] == join(
#         settings.STORAGE_BASE_URL,
#         workspace.slug,
#         "avatar",
#         slugify(account.username) + splitext(fpath)[1],
#     )

#     response1 = client.get(profile["profile"]["avatar"])
#     assert response1.status_code == 200
#     assert response1.content.decode("utf-8") == file_content

#     # Cleanup files.
#     remove(fpath)
#     remove(profile["profile"]["avatar"].replace(settings.STORAGE_BASE_URL, settings.STORAGE_PATH))


# def test_update_profile_avatar_without_profile(
#     client: TestClient, session: Session, faker: Faker
# ) -> None:
#     workspace, account, headers = create_random_workspace_and_account_with_token(
#         client, session, role=AccountRole.admin
#     )
#     file_content = faker.text()
#     fname = faker.file_name(extension="txt")
#     fpath = join("./tmp", fname)
#     makedirs("./tmp", exist_ok=True)
#     with open(fpath, "w") as f:
#         f.write(file_content)

#     with open(fpath, "rb") as f:
#         response = client.put(
#             f"{settings.API_V1_STR}/{workspace.slug}/profiles/avatar",
#             files={"avatar": (fname, f, "image/jpeg")},
#             headers=headers,
#         )
#     assert response.status_code == 404
#     assert response.json()["detail"] == "Specified profile could not be found"

#     remove(fpath)
