import random
import string
from typing import Dict

from fastapi.testclient import TestClient

from app.core.config import settings


def random_lower_string(length=32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def random_email() -> str:
    return f"{random_lower_string(10)}@{random_lower_string(8)}.com"


def random_phone_number() -> str:
    return "".join(random.choices(string.digits, k=12))


def random_dict() -> Dict[str, str]:
    dict = {}
    for _ in range(random.randint(1, 10)):
        dict[random_lower_string(8)] = random_lower_string()

    return dict


def get_superuser_token_headers(client: TestClient) -> Dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers
