---
title: Account management
summary: Account and profile routing, typed actions, and starter usage patterns for the template.
---

# Account management

The template includes the public `msflib.account` functionality through the app’s model and router layer. The project exposes `AccountAction` and `ProfileAction` from `app.actions` and re-exports account and profile models from `app.models`.

## Purpose

This module handles:

- registration and account creation
- current account read/update flows
- profile retrieval and mutation
- admin access patterns for account management

## Installation and requirements

The repo already includes account support in dependencies:

```toml
[tool.poetry.dependencies]
msflib = { git = "https://github.com/msflib/fastapi.git", subdirectory = "core", rev = "dev" }
msflib-account = { git = "https://github.com/msflib/fastapi.git", subdirectory = "modules/account", rev = "dev" }
```

The application also expects these values to be present in the environment:

- `SECRET_KEY`
- `FIRST_SUPERUSER`
- `FIRST_SUPERUSER_PASSWORD`
- `USERS_OPEN_REGISTRATION`
- `ALLOW_WORKSPACE_REGISTRATION`

## Public API overview

| Name | Signature | Params | Returns | Description |
|------|-----------|--------|---------|-------------|
| `AccountAction` | `AccountAction[Account, AccountCreate, AccountUpdate](settings=settings)` | settings, service model types | action service | Performs account create/read/update workflows |
| `ProfileAction` | `ProfileAction[Profile, ProfileCreate, ProfileUpdate]()` | optional config | action service | Handles profile lifecycle logic |
| `account_router` | `account_router(...)` | session, current account, settings, account/profile models | `APIRouter` | Registers account and profile endpoints |
| `profile_router` | `profile_router(...)` | session, current account, profile model types | `APIRouter` | Registers profile endpoints |

## Example: mount account routers

```python
from msflib.account.router import account_router, profile_router
from app.api import deps
from app import models
from app.core.config import settings

api_router.include_router(
    account_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        settings=settings,
        account_type=models.Account,
        profile_type=models.Profile,
        account_read_type=models.AccountRead,
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
```

## Example: use the action layer

```python
from app.actions import account_action, profile_action

account = account_action.create(
    email="alice@example.com",
    password="StrongPassword!123",
    is_active=True,
)

profile = profile_action.create(
    account_id=account.id,
    full_name="Alice Example",
    avatar_url="https://example.com/avatar.png",
)

print(account.email, profile.full_name)
```

## Example: current account access

```python
from fastapi import Depends
from app.api.deps import get_current_account

@app.get("/account/me")
def current_account(current_account=Depends(get_current_account)):
    return {
        "id": current_account.id,
        "email": current_account.email,
    }
```

## Example failure handling

```python
from fastapi import HTTPException

try:
    account_action.create(email="bad-email", password="short")
except ValueError as exc:
    print("validation failed:", exc)
```

Common issues include:

- invalid email format
- duplicate email or username values
- disallowed registration when `USERS_OPEN_REGISTRATION` is disabled

## Config and environment

This module is config-driven by the app settings, with most runtime behavior controlled through:

- `USERS_OPEN_REGISTRATION`
- `SECRET_KEY`
- `PASSWORD_RESET_PATH`
- account role and status configuration in the underlying `msflib` package

## See also

- [Authentication](auth.md)
- [Core configuration](core.md)
- [Workspaces](workspaces.md)
- [Quickstart](index.md)
