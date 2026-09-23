---
title: Workspaces and users
summary: Workspace and user actions, starter usage, and integration examples for the FastAPI template.
---

# Workspaces and users

This template includes the workspace layer from the public `msflib.workspaces` package. In the application, the workspace and user action classes are exported from `app.actions` and the workspace/user models are re-exported through `app.models`.

## Purpose

The workspace module is used to manage:

- workspace creation and membership
- user records associated with accounts
- organization or project-level permissions
- typed action flows for CRUD and workspace business logic

## Installation and requirements

The template configures the workspace package via Poetry:

```toml
[tool.poetry.dependencies]
msflib = { git = "https://github.com/msflib/fastapi.git", subdirectory = "core", rev = "dev" }
msflib-workspaces = { git = "https://github.com/msflib/fastapi.git", subdirectory = "modules/workspaces", rev = "dev" }
```

If the project enables workspace registration, values such as `ALLOW_WORKSPACE_REGISTRATION` and `SECRET_KEY` should be validated before startup.

## Public API overview

| Name | Signature | Params | Returns | Description |
|------|-----------|--------|---------|-------------|
| `WorkspaceAction` | `WorkspaceAction[Workspace, WorkspaceCreate, WorkspaceUpdate](settings=settings)` | settings and typed models | action service | Manages workspace create/update flows |
| `UserAction` | `UserAction[User, UserCreate, UserUpdate]()` | typed models | action service | Manages workspace user records |
| `Workspace` | `Workspace` | properties from schema | model instance | Represents a workspace/project entity |
| `User` | `User` | account + workspace metadata | model instance | Represents a user inside a workspace |

## Example: register workspace actions

```python
from msflib.workspaces.actions import WorkspaceAction, UserAction
from app.core.config import settings
from app.models import User, UserCreate, UserUpdate, Workspace, WorkspaceCreate, WorkspaceUpdate

workspace_action = WorkspaceAction[Workspace, WorkspaceCreate, WorkspaceUpdate](settings=settings)
user_action = UserAction[User, UserCreate, UserUpdate]()
```

## Example: create a workspace

```python
workspace = workspace_action.create(
    name="Acme Platform",
    slug="acme-platform",
    owner_id=account.id,
)

print(workspace.name, workspace.slug)
```

## Example: create a workspace user

```python
user = user_action.create(
    account_id=account.id,
    workspace_id=workspace.id,
    role="member",
)

print(user.account_id, user.workspace_id)
```

## Example: failure handling

```python
try:
    workspace_action.create(name="", slug="bad slug", owner_id=None)
except ValueError as exc:
    print("workspace validation failed:", exc)
```

Typical failures include:

- duplicate workspace slug
- missing owner account
- invalid workspace metadata or required fields

## Config and environment

In the starter app, workspace behavior is configured through the shared settings layer in `app/core/config.py`. The environment example includes:

- `ALLOW_WORKSPACE_REGISTRATION`
- `SECRET_KEY`
- `POSTGRES_*` and `REDIS_*` settings for backing store connectivity

## See also

- [Account management](account.md)
- [Authentication](auth.md)
- [Core configuration](core.md)
- [Quickstart](index.md)
