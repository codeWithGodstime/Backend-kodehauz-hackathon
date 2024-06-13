from typing import List

from sqlmodel import Session, select

from app.actions import Action
from app.models.account import Account
from app.models.profile import Profile, ProfileCreate, ProfileUpdate


class ActionProfile(Action[Profile, ProfileCreate, ProfileUpdate]):
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


profile = ActionProfile()
