from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from .api.api_v1.api import api_router
from .core.config import settings
from .bootstrap import bootstrap_module_hooks

bootstrap_module_hooks()

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# Static location for upload files.
if settings.STORAGE_METHOD == "file":
    app.mount(
        settings.STORAGE_BASE_URL,
        StaticFiles(directory=settings.STORAGE_PATH),
        name="storage",
    )
