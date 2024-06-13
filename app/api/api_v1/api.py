from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    accounts,
    admin,
    auth,
    profiles,
    sse_stream,
)

# Non-admin routes
api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(accounts.router, tags=["accounts"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])

# Admin routes
api_router.include_router(admin.router, prefix="/admin")
api_router.include_router(admin.wsrouter, prefix="/admin")

# Streaming route
api_router.include_router(sse_stream.router)
