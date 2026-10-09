---
title: Authentication
summary: JWT auth, account dependency wiring, and router setup for the template.
---

# Authentication

The template mounts the public `msflib.auth` router and dependency factories to provide login, logout, password recovery, and account-scoped access control. The actual wiring is done in `app/api/api_v1/api.py` and `app/api/deps.py`.

## Purpose

This module is responsible for:

- issuing and validating access tokens
- authenticating the current account
- exposing login and password reset endpoints
- tying auth flows to the app-specific `Account` model and settings

## Installation and requirements

The template already brings in the auth package via Poetry:

```toml
[tool.poetry.dependencies]
msflib = { git = "https://github.com/msflib/fastapi.git", subdirectory = "core", rev = "dev" }
msflib-auth = { git = "https://github.com/msflib/fastapi.git", subdirectory = "modules/auth", rev = "dev" }
```

The app also requires the following runtime values:

- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `INVALID_JWT_EXPIRE`
- `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD` for initial bootstrapping

## Public API overview

| Name | Signature | Params | Returns | Description |
|------|-----------|--------|---------|-------------|
| `get_account_dependencies` | `get_account_dependencies(...)` | `AccountModel`, `oauth_token_url`, `secret_key`, `session_dep`, `keystore_dep` | dependency bundle | Builds auth dependencies for account-based access control |
| `auth_router` | `auth_router(...)` | `get_session`, `get_keystore`, `get_current_account`, `settings`, `account_type`, `account_read_type` | `APIRouter` | Registers login/logout and password reset routes |
| `get_current_account` | `get_current_account` | depends on request state and token | current account | Resolves the authenticated active account |

## Example: enable auth router

The template mounts the auth router like this:

```python
from msflib.auth.router import router as auth_router
from app.core.config import settings
from app.api import deps
from app import models

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
```

## Example: build account dependencies

```python
from msflib.auth.deps import get_account_dependencies
from app.api.deps import get_session, get_keystore
from app.core.config import settings
from app.models import Account, AccountStatus

account_dependencies = get_account_dependencies(
    AccountModel=Account,
    oauth_token_url=f"{settings.API_V1_STR}/login",
    secret_key=settings.SECRET_KEY,
    active_statuses=[AccountStatus.active, AccountStatus.online],
    session_dep=get_session,
    keystore_dep=get_keystore,
)

get_current_account = account_dependencies.get_current_account
```

## Example: protect a route

```python
from fastapi import Depends, FastAPI
from app.api.deps import get_current_account

app = FastAPI()

@app.get("/profile")
def profile(current_account=Depends(get_current_account)):
    return {"email": current_account.email}
```

This pattern is consistent with the project’s actual dependency wiring in `app/api/deps.py`.

## Example failure handling

```python
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

try:
    account = get_current_account(credentials)
except HTTPException as exc:
    print("Authentication failed:", exc.detail)
```

Common causes include:

- expired JWT tokens
- invalid `Authorization` header
- account status not in the allowed `active_statuses`

## Config and environment

The auth layer relies on the application settings object declared in `app/core/config.py`, especially:

- `SECRET_KEY`
- `API_V1_STR`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `PASSWORD_RESET_PATH`

The example `.env-example` file defines the most relevant values for local development.

## See also

- [Core configuration](core.md)
- [Account management](account.md)
- [Quickstart](index.md)
