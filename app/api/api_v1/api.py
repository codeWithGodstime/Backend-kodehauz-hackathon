from fastapi import APIRouter

from msflib.auth.router import router as create_auth_router

from app.api.api_v1.endpoints import (
    accounts,
    admin,
    auth,
    profiles,
    sse_stream,
)

# Module routers.
auth_router = create_auth_router(
    get_session=deps.get_session,
    get_keystore=deps.get_keystore,
    get_current_account=deps.get_current_account,
    account_type=models.Account,
    settings=settings,
    active_statuses=[models.AccountStatus.active, models.AccountStatus.online],
    prefix="",
    account_read_type=models.AccountRead,
    access_token_decorator=auth.access_token_decorator,
    access_token_response_type=schemas.Token,
)

# Non-admin routes
api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(accounts.router, tags=["accounts"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])

# Admin routes
api_router.include_router(admin.router, prefix="/admin")
# api_router.include_router(admin.wsrouter, prefix="/admin")

# Streaming route
api_router.include_router(sse_stream.router)
