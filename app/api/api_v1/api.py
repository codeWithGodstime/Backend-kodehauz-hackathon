from fastapi import APIRouter
from msflib.account.router import account_router, profile_router
from msflib.auth.router import router as auth_router
from msflib.payments.router import router as payments_router
from msflib.workspaces.router import router as workspace_router
from msflib.workspaces.router import user_me_router

from app import actions, models
from app.api import deps
from app.api.api_v1.endpoints import admin, billing, dashboard, webhooks, workspaces
from app.core.config import settings
from app.eventbus.signup_workspace import SignupAccountCreate, signup_account_action

api_router = APIRouter()

api_router.include_router(
    auth_router(
        get_session=deps.get_session,
        get_keystore=deps.get_keystore,
        get_current_account=deps.get_current_account,
        account_type=models.Account,
        account_read_type=models.AccountRead,
        settings=settings,
        active_statuses=[models.AccountStatus.active, models.AccountStatus.online],
        prefix="",
        tags=["auth"],
    )
)

api_router.include_router(
    account_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        settings=settings,
        account_type=models.Account,
        profile_type=models.Profile,
        account_read_type=models.AccountRead,
        account_create_type=SignupAccountCreate,
        account_action=signup_account_action,
        prefix="",
        tags=["accounts"],
    )
)

api_router.include_router(
    profile_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        get_current_active_account=deps.get_current_active_account,
        settings=settings,
        profile_type=models.Profile,
        account_type=models.Account,
        profile_read_type=models.ProfileRead,
        prefix="/profiles",
        tags=["profiles"],
    )
)

api_router.include_router(admin.router, prefix="/admin")
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(workspaces.router, tags=["workspaces"])
api_router.include_router(
    workspace_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        get_current_account_or_none=deps.get_current_account_or_none,
        role_check=deps.RoleCheck,
        settings=settings,
        account_type=models.Account,
        workspace_type=models.Workspace,
        user_type=models.User,
        workspace_action=actions.workspace_action,
        user_action=actions.user_action,
    )
)
api_router.include_router(
    user_me_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        get_current_active_account=deps.get_current_active_account,
        get_current_workspace=deps.get_current_workspace,
        user_type=models.User,
        user_action=actions.user_action,
    )
)
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(
    payments_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        settings=settings,
        prefix="/payments",
    )
)
