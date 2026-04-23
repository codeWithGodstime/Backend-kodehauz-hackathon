from sqlmodel import Session

from app.actions import profile_action as pa, account_action as aa
from app.models.profile import ProfileUpdate
from app.tests.utils.utils import random_lower_string


def test_create_profile(session: Session) -> None:
    first_name = random_lower_string()
    last_name = random_lower_string()
    data = pa.random(first_name=first_name, last_name=last_name)
    account = aa.create_random(session, profile=data)
    assert account.profile.first_name == first_name
    assert account.profile.last_name == last_name
    assert account.profile.id == account.id


def test_get_profile(session: Session) -> None:
    account = aa.create_random(session, profile=pa.random())
    stored_profile = pa.get(session=session, id=account.profile.id)
    assert stored_profile
    assert account.profile.id == stored_profile.id
    assert account.profile.first_name == stored_profile.first_name
    assert account.profile.last_name == stored_profile.last_name
    assert account.profile.gender == stored_profile.gender
    assert account.profile.marital_status == stored_profile.marital_status
    # assert profile.address == stored_profile.address
    # assert profile.address_id == stored_profile.address_id
    assert account.profile.id == stored_profile.id
    assert account.profile.account == stored_profile.account


def test_update_profile(session: Session) -> None:
    account = aa.create_random(session, profile=pa.random())
    first_name = random_lower_string()
    profile_update = ProfileUpdate(first_name=first_name)
    profile2 = pa.update(session=session, model=account.profile, data=profile_update)
    assert account.profile.id == profile2.id
    assert account.profile.last_name == profile2.last_name
    assert profile2.first_name == first_name
    assert account.profile.id == profile2.id


def test_delete_profile(session: Session) -> None:
    account = aa.create_random(session, profile=pa.random())
    profile = account.profile
    profile2 = pa.delete(session=session, id=profile.id)
    profile3 = pa.get(session=session, id=profile.id)
    assert profile3 is None
    assert profile2.id == profile.id
    assert profile2.first_name == profile.first_name
    assert profile2.last_name == profile.last_name
    assert profile2.gender == profile.gender
    assert profile2.marital_status == profile.marital_status
    assert profile2.id == account.id
