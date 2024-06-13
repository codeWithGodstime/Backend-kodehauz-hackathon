from sqlmodel import Session

from app import actions
from app.models.profile import ProfileUpdate
from app.tests.utils.account import create_random_account
from app.tests.utils.profile import create_random_profile, random_profile_create
from app.tests.utils.utils import random_lower_string


def test_create_profile(session: Session) -> None:
    first_name = random_lower_string()
    last_name = random_lower_string()
    data = random_profile_create(first_name=first_name, last_name=last_name)
    account = create_random_account(session)
    profile = actions.profile.create_with_owner(session=session, data=data, account=account)
    assert profile.first_name == first_name
    assert profile.last_name == last_name
    assert profile.id == account.id


def test_get_profile(session: Session) -> None:
    account = create_random_account(session)
    profile = create_random_profile(session, account=account)
    stored_profile = actions.profile.get(session=session, id=profile.id)
    assert stored_profile
    assert profile.id == stored_profile.id
    assert profile.first_name == stored_profile.first_name
    assert profile.last_name == stored_profile.last_name
    assert profile.gender == stored_profile.gender
    assert profile.marital_status == stored_profile.marital_status
    # assert profile.address == stored_profile.address
    # assert profile.address_id == stored_profile.address_id
    assert profile.id == stored_profile.id
    assert profile.account == stored_profile.account


def test_update_profile(session: Session) -> None:
    account = create_random_account(session)
    profile = create_random_profile(session, account=account)
    first_name = random_lower_string()
    profile_update = ProfileUpdate(first_name=first_name)
    profile2 = actions.profile.update(session=session, model=profile, data=profile_update)
    assert profile.id == profile2.id
    assert profile.last_name == profile2.last_name
    assert profile2.first_name == first_name
    assert profile.id == profile2.id


def test_delete_profile(session: Session) -> None:
    account = create_random_account(session)
    profile = create_random_profile(session, account=account)
    profile2 = actions.profile.delete(session=session, id=profile.id)
    profile3 = actions.profile.get(session=session, id=profile.id)
    assert profile3 is None
    assert profile2.id == profile.id
    assert profile2.first_name == profile.first_name
    assert profile2.last_name == profile.last_name
    assert profile2.gender == profile.gender
    assert profile2.marital_status == profile.marital_status
    assert profile2.id == account.id
