from typing import Any, Dict, Optional, Callable

from sqlmodel import Session, select

from app.actions import Action
from app.core.security import get_password_hash, verify_password
from app.models.account import Account, AccountCreate, AccountUpdate


class ActionAccount(Action[Account, AccountCreate, AccountUpdate]):
    def get_by_email(self, session: Session, *, email: str) -> Optional[Account]:
        return session.exec(select(Account).where(Account.email == email.lower())).first()

    def create(
        self,
        session: Session,
        *,
        data: AccountCreate,
        update: Optional[Dict[str, Any]] = {},
    ) -> Account:
        def callback(account: Account) -> Account:
            account.hashed_password = get_password_hash(data.password)
            account.email = account.email.lower()

        return super().create(session, data=data, update=update, decorator=callback)

    def update(
        self,
        session: Session,
        *,
        model: Account,
        data: Optional[AccountUpdate] = None,
        update: Optional[Dict[str, Any]] = {},
        decorator: Callable[[Account], Any] = None,
    ) -> Account:
        update_data = data.dict(exclude_unset=True) if data is not None else {}
        update_data = {**update_data, **update}
        if update_data.get("password"):
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        return super().update(session, model=model, update=update_data)

    def authenticate(self, session: Session, *, email: str, password: str) -> Optional[Account]:
        account = self.get_by_email(session, email=email)
        if not account:
            return None
        if not verify_password(password, account.hashed_password):
            return None
        return account


account = ActionAccount()
