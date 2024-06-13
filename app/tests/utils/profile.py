from sqlmodel import Session

from app import actions
from app.models.account import Account
from app.models.profile import Profile, ProfileCreate

from app.tests.utils.utils import random, random_lower_string
from app.models.profile import Gender, MaritalStatus

from faker import Faker


def create_random_profile(session: Session, account: Account, **data: dict) -> Profile:
    create_data = random_profile_create(**data)
    profile = actions.profile.create(session=session, data=create_data, update={"id": account.id})
    return profile


def random_profile_create(**data: dict) -> ProfileCreate:
    fake = Faker()
    return ProfileCreate(
        first_name=data.get("first_name", random_lower_string().title()),
        last_name=data.get("last_name", random_lower_string().title()),
        date_of_birth=data.get("date_of_birth", fake.date(pattern="%Y-%m-%d")),
        gender=data.get("gender", random.choice(list(Gender))),
        marital_status=data.get("marital_status", random.choice(list(MaritalStatus))),
    )
