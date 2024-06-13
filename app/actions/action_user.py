from typing import Optional

from sqlmodel import Session, select

from app.actions import Action, account
from app.models.user import User, UserCreate, UserUpdate


class ActionUser(Action[User, UserCreate, UserUpdate]):
    def get_by_email(self, session: Session, *, email: str) -> Optional[User]:
        acc = account.get_by_email(session=session, email=email)
        return session.exec(select(User).where(User.account_id == acc.id)).first()


user = ActionUser()
