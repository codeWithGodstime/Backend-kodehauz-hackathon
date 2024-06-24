from fastapi import APIRouter

from . import accounts

# Admin routes.
router = APIRouter()
router.include_router(accounts.router, prefix="/accounts", tags=["admin", "accounts"])
