from msflib.account.actions import AccountAction, ProfileAction
from msflib.workspaces.actions import WorkspaceAction, UserAction

from ..core.config import settings
from ..models import (
    Account,
    AccountCreate,
    AccountUpdate,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    User,
    UserCreate,
    UserUpdate,
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
)

account_action = AccountAction[Account, AccountCreate, AccountUpdate](settings=settings)

profile_action = ProfileAction[Profile, ProfileCreate, ProfileUpdate]()

workspace_action = WorkspaceAction[Workspace, WorkspaceCreate, WorkspaceUpdate](settings=settings)

user_action = UserAction[User, UserCreate, UserUpdate]()
