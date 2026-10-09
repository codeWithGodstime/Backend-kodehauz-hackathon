---
title: Core configuration and bootstrap
summary: Shared settings, database startup, and FastAPI app bootstrap used by the template.
---

# Core configuration

The core layer in this template is a thin application configuration wrapper over the public `msflib` settings classes. The actual settings object is assembled in `app/core/config.py` and used by the auth, account, and workspace services.

## Purpose

This module provides the central place for:

- secret keys and server metadata
- database configuration
- Redis and file-storage settings
- CORS and auth expirations
- support for workspace and account-specific settings

## Settings composition

The application builds a combined settings class:

```python
from typing import Optional

from msflib.core.config import CoreSettings, SettingsBase
from msflib.auth.config import AuthSettings
from msflib.account.config import AccountSettings
from msflib.workspaces.config import WorkspaceSettings


class AppSettings(WorkspaceSettings, AccountSettings, AuthSettings, CoreSettings, SettingsBase):
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    INVALID_JWT_EXPIRE: Optional[int] = 3600
    EMAIL_TEMPLATES_DIR: str = "./app/email-templates/build"
    PASSWORD_RESET_PATH: str = "/password-reset"
```

This pattern makes the app flexible while keeping each public `msflib` module responsible for its own config surface.

## Environment variables

The template reads many of these values from `.env`, using the example file as the source of truth:

| Name | Example | Purpose |
|------|---------|---------|
| `SECRET_KEY` | `your-secret-key` | JWT signing and session security |
| `POSTGRES_SERVER` | `localhost` | Database host |
| `POSTGRES_USER` | `postgres` | Postgres login |
| `POSTGRES_PASSWORD` | `postgres` | Postgres password |
| `POSTGRES_DB` | `dbname` | Database name |
| `USE_SQLITE` | `false` | Use SQLite instead of Postgres |
| `REDIS_HOST` | `localhost` | Redis host for keystore support |
| `REDIS_PORT` | `6379` | Redis port |
| `STORAGE_METHOD` | `file` | File upload backend |
| `STORAGE_PATH` | `uploads` | Local upload directory |
| `BACKEND_CORS_ORIGINS` | `[...]` | Allowed browser origins |

## Database setup

The project creates a SQLModel engine in `app/db/session.py`:

```python
from sqlmodel import create_engine, Session
from msflib.core.config import CoreSettings
from app.core.config import settings

core_settings: CoreSettings = settings.scope("CORE")
if core_settings.USE_SQLITE:
    engine = create_engine(
        core_settings.SQLITE_DATABASE_URI,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=core_settings.DB_DEBUG_MODE,
    )
else:
    engine = create_engine(
        str(core_settings.SQLALCHEMY_DATABASE_URI),
        pool_pre_ping=True,
        echo=core_settings.DB_DEBUG_MODE,
    )
```

This means the application can run against a Postgres-backed production setup or a local SQLite database for rapid iteration.

## FastAPI bootstrap

The app is built in `app/main.py` and includes the generated auth/account/workspace routers:

```python
from fastapi import FastAPI
from .api.api_v1.api import api_router
from .core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")
app.include_router(api_router, prefix=settings.API_V1_STR)
```

The app also mounts static uploads when `STORAGE_METHOD == "file"`:

```python
if settings.STORAGE_METHOD == "file":
    app.mount(
        settings.STORAGE_BASE_URL,
        StaticFiles(directory=settings.STORAGE_PATH),
        name="storage",
    )
```

## Dependencies and auth wiring

The shared dependency layer lives in `app/api/deps.py`:

```python
from msflib.api.deps import get_keystore_factory, get_session_factory
from msflib.auth.deps import get_account_dependencies

get_session = get_session_factory(engine)
get_keystore = get_keystore_factory(
    redis_host=settings.REDIS_HOST,
    redis_password=settings.REDIS_PASSWORD,
    redis_port=int(settings.REDIS_PORT) if settings.REDIS_PORT else 6379,
)
```

This is then used to produce the dependency functions that enforce account and auth checks for the endpoints.

## Troubleshooting

### Missing environment values

If the app reports missing config values, verify that `.env` exists and has the correct keys. The project ships with `.env-example` as a template.

### Auth or DB connection issues

- Confirm PostgreSQL credentials match the running database.
- Check Redis settings if `get_keystore` fails.
- If using SQLite, ensure `USE_SQLITE=true` and the URI is valid.

## See also

- [Authentication](auth.md)
- [Account management](account.md)
- [Workspaces](workspaces.md)
- [Quickstart](index.md)
