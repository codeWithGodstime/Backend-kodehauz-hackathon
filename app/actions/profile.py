from typing import List

from faker import Faker
from sqlmodel import Session, select

from app.actions import ModelAction
from app.models.account import Account
from app.models.profile import Profile, ProfileCreate, ProfileUpdate

from app.tests.utils.utils import random, random_lower_string
from app.models.profile import Gender, MaritalStatus


class ActionProfile(ModelAction[Profile, ProfileCreate, ProfileUpdate]):
    def create_with_owner(
        self, session: Session, *, data: ProfileCreate, account: Account
    ) -> Profile:
        return super().create(session, data=data, update={"id": account.id})

    def get_multi_by_owner(
        self, session: Session, *, account: Account, skip: int = 0, limit: int = 100
    ) -> List[Profile]:
        return session.exec(
            select(Profile).where(Profile.id == account.id).offset(skip).limit(limit)
        ).all()

    def random(self, **data: dict) -> ProfileCreate:
        fake = Faker()
        return ProfileCreate(
            first_name=data.get("first_name", random_lower_string().title()),
            last_name=data.get("last_name", random_lower_string().title()),
            date_of_birth=data.get("date_of_birth", fake.date(pattern="%Y-%m-%d")),
            gender=data.get("gender", random.choice(list(Gender))),
            marital_status=data.get("marital_status", random.choice(list(MaritalStatus))),
        )


profile = ActionProfile()
