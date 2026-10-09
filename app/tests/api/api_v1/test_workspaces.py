from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import workspace_action
from app.core.config import settings


def test_workspace_catalog_routes_are_not_missing(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    owned = workspace_action.get_multi_by_all(session, limit=5)
    assert owned
    slug = owned[0].slug

    listed = client.get(
        f"{settings.API_V1_STR}/workspaces",
        headers=superuser_account_token_headers,
    )
    available = client.get(
        f"{settings.API_V1_STR}/workspaces/available",
        headers=superuser_account_token_headers,
    )

    assert listed.status_code == 200
    assert available.status_code == 200
    listed_body = listed.json()
    available_body = available.json()
    assert isinstance(listed_body, list)
    assert isinstance(available_body, list)
    assert any(row["slug"] == slug for row in listed_body)
    assert any(row["slug"] == slug for row in available_body)
    sample = listed_body[0]
    assert sample["id"]
    assert sample["name"]
    assert sample["label"] == sample["name"]
    assert "logo" in sample
    assert "registration_link" in sample
    assert "publish_to_users" in sample
    assert "start_date" in sample
    assert "end_date" in sample


def test_workspace_catalog_requires_auth(client: TestClient) -> None:
    listed = client.get(f"{settings.API_V1_STR}/workspaces")
    available = client.get(f"{settings.API_V1_STR}/workspaces/available")
    assert listed.status_code in {401, 403}
    assert available.status_code in {401, 403}
