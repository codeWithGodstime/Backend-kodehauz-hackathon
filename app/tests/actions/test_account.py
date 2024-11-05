from sqlmodel import Session

from app.actions import account as aa
from app.core.security import verify_password
from app.models.account import Account, AccountRole, AccountUpdate, AccountStatus
from app.tests.utils.utils import random_email, random_lower_string


def test_create_account(session: Session) -> None:
    data = aa.random()
    data.email = data.email.upper()
    account = aa.create(session, data=data)
    assert account.email == data.email.lower()
    assert hasattr(account, "hashed_password")


def test_authenticate_account(session: Session) -> None:
    data = aa.random()
    account = aa.create(session, data=data)
    authenticated_account = aa.authenticate(session, email=data.email, password=data.password)
    assert authenticated_account
    assert account.email == authenticated_account.email


def test_not_authenticate_account(session: Session) -> None:
    email = random_email()
    password = random_lower_string()
    account = aa.authenticate(session, email=email, password=password)
    assert account is None


def test_check_if_account_is_active(session: Session) -> None:
    account_in = aa.random()
    account = aa.create(session, data=account_in)
    assert account.status == AccountStatus.active


def test_check_if_account_is_active_inactive(session: Session) -> None:
    account_in = aa.random(is_superaccount=True)
    account = aa.create(session, data=account_in)
    assert account.status == AccountStatus.active


def test_check_if_account_is_superaccount(session: Session) -> None:
    account = aa.create_random(session, role=AccountRole.admin)
    assert account.role == AccountRole.admin


def test_check_if_account_is_superaccount_normal_account(session: Session) -> None:
    account = aa.create_random(session)
    assert account.role == AccountRole.user


def test_get_account(session: Session) -> None:
    account_in = aa.random(is_superaccount=True)
    account = aa.create(session, data=account_in)
    account_2 = aa.get(session, id=account.id)
    assert account_2
    assert account.email == account_2.email
    assert account.jsond() == account_2.jsond()


def test_update_account(session: Session) -> None:
    account_in = aa.random(is_superaccount=True)
    account = aa.create(session, data=account_in)
    new_password = random_lower_string()
    account_in_update = AccountUpdate(password=new_password, is_superaccount=True)
    aa.update(session, model=account, data=account_in_update)
    account_2 = aa.get(session, id=account.id)
    assert account_2
    assert account.email == account_2.email
    assert verify_password(new_password, account_2.hashed_password)


def test_get_account_by_any_filter(session: Session) -> None:
    accounts = [aa.create_random(session) for i in range(5)]
    account = aa.get_by_any(
        session,
        username="__doesnt exist_",
        email=accounts[4].email,
    )
    assert account
    assert account.email == accounts[4].email
    account_2 = aa.get_by_any(
        session,
        username=accounts[2].username,
        phone=accounts[2].email,
    )
    assert account_2
    assert account_2.email == accounts[2].email
    account_3 = aa.get_by_any(
        session,
        username=accounts[0].hashed_password,
        phone=accounts[0].email,
    )
    assert account_3 is None


def test_get_account_by_all_filter(session: Session) -> None:
    accounts = [aa.create_random(session) for i in range(5)]
    account = aa.get_by_all(
        session,
        username=accounts[4].username,
        email=accounts[4].email,
    )
    assert account
    assert account.email == accounts[4].email
    account_2 = aa.get_by_all(
        session,
        username=accounts[2].username,
        phone=accounts[3].phone,
    )
    assert account_2 is None
    account_3 = aa.get_by_all(
        session,
        username=accounts[0].username,
        email=None,
    )
    assert account_3 is None


def test_get_account_by_expressions(session: Session) -> None:
    accounts = [aa.create_random(session) for i in range(5)]
    account = aa.get_by_expressions(
        session,
        Account.username == accounts[2].username,
        Account.email == accounts[2].email,
    )
    assert account
    assert account.email == accounts[2].email
    account_2 = aa.get_by_expressions(
        session,
        Account.username == accounts[2].username,
        Account.phone == accounts[3].phone,
    )
    assert account_2 is None
    account_3 = aa.get_by_expressions(
        session,
        Account.username == accounts[0].username,
        Account.email == None,  # noqa
    )
    assert account_3 is None


def test_change_password(session: Session) -> None:
    account = aa.create_random(session)
    uuu = {
        "id": account.id,
        "email": account.email,
        "hashed_password": account.hashed_password,
    }
    data = AccountUpdate(password="new password", email=random_email())
    account_1 = aa.update(session, model=account, data=data)

    assert account_1.id == uuu["id"]
    assert account_1.hashed_password != uuu["hashed_password"]
    assert verify_password(data.password, account_1.hashed_password)

    account_2 = aa.get(session, id=uuu["id"])
    assert account_2.id == uuu["id"]
    assert account_2.hashed_password != uuu["hashed_password"]
    assert verify_password(data.password, account_2.hashed_password)


def test_change_other_attrs(session: Session) -> None:
    account = aa.create_random(session)
    uuu = account.dict()
    data = AccountUpdate(username=random_lower_string(), phone=random_lower_string())
    account_1 = aa.update(session, model=account, data=data)

    assert account_1.id == uuu["id"]
    assert account_1.username != uuu["username"]
    assert account_1.phone != uuu["phone"]
