import os
import sys
import subprocess
from pathlib import Path

from unittest.mock import patch
from sqlmodel import Session

from app.initial_data import init, main
from app.db.session import engine as production_engine
from app.actions import account_action as aa, user_action as ua
from app.core.config import settings
from app.db.init_db import init_db
from app.models import Workspace
from app.tests.conftest import engine as test_engine


# Test that `init_db` is called with correct arguments
@patch("app.initial_data.init_db")
@patch("app.initial_data.Session")
def test_init(mock_session, mock_init_db):
    # Call init function
    init()

    # Check that Session is created and closed
    mock_session.assert_called_once_with(production_engine)

    # Verify `init_db` was called with a non-destructive default.
    mock_init_db.assert_called_once_with(production_engine, create_tables=False)


# 2. Test Logging Messages
@patch("app.initial_data.logger")
@patch("app.initial_data.init")
def test_main_logging(mock_init, mock_logger):
    # Run main function
    main()

    # Verify logging calls
    mock_logger.info.assert_any_call("Creating initial data")
    mock_logger.info.assert_any_call("Initial data created")
    mock_init.assert_called_once()


def test_init_db_creates_default_workspace_for_superuser() -> None:
    init_db(test_engine, create_tables=True)

    with Session(test_engine) as session:
        account = aa.get_by_email(session, email=settings.FIRST_SUPERUSER)

        assert account is not None
        assert account.current_workspace_id is not None

        workspace = session.get(Workspace, account.current_workspace_id)
        assert workspace is not None
        membership = ua.get_by_all(
            session,
            account_id=account.id,
            workspace_id=workspace.id,
        )
        assert membership is not None
        assert workspace.is_default is True


def test_initial_data_cli_creates_default_workspace_for_superuser() -> None:
    env = os.environ.copy()
    env.update(
        {
            "USE_SQLITE": "true",
            "SQLITE_DATABASE_URI": str(test_engine.url),
            "CORE__USE_SQLITE": "true",
            "CORE__SQLITE_DATABASE_URI": str(test_engine.url),
            "CORE__SQLALCHEMY_DATABASE_URI": "",
            "FIRST_SUPERUSER": settings.FIRST_SUPERUSER,
            "FIRST_SUPERUSER_PASSWORD": settings.FIRST_SUPERUSER_PASSWORD,
            "ACCOUNT__FIRST_SUPERUSER": settings.FIRST_SUPERUSER,
            "ACCOUNT__FIRST_SUPERUSER_PASSWORD": settings.FIRST_SUPERUSER_PASSWORD,
            "INITIAL_DATA_RESET_DB": "true",
        }
    )

    repo_root = Path(__file__).resolve().parents[3]
    subprocess.run(
        [sys.executable, "-m", "app.initial_data"],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    with Session(test_engine) as session:
        account = aa.get_by_email(session, email=settings.FIRST_SUPERUSER)

        assert account is not None
        assert account.current_workspace_id is not None

        workspace = session.get(Workspace, account.current_workspace_id)
        assert workspace is not None
        membership = ua.get_by_all(
            session,
            account_id=account.id,
            workspace_id=workspace.id,
        )
        assert membership is not None
        assert workspace.is_default is True
