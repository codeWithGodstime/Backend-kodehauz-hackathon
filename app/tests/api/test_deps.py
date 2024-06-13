from typing import Tuple

import pytest
from sqlmodel import Session

from app.api import deps
from app.tests.utils.account import create_random_account

statuses = {"online": True, "active": True, "suspended": False, "banned": False}


@pytest.mark.parametrize("status", statuses.items(), ids=statuses.keys())
def test_get_active_accounts(session: Session, status: Tuple[str, bool]) -> None:
    account = create_random_account(session, status=status[0])
    try:
        account = deps.get_current_active_account(account)
        assert status[1] is True
    except Exception:
        assert status[1] is False
