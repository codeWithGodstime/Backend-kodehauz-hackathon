---
title: MSF FastAPI Template
summary: Quickstart and integration guide for the MSF FastAPI starter application.
---

# MSF FastAPI Template

This repository is a starter application for building a FastAPI service on top of the public `msflib` packages. It wires together the core library, auth module, account module, and workspace features through a small application layer in `app/`.

## What this template includes

- FastAPI application bootstrap via `app.main:app`
- Shared settings in `app/core/config.py`
- Auth, account, and profile routers from `msflib`
- Workspace and user actions from `msflib.workspaces`
- SQLModel database session setup and config-driven environment loading
- A ready-to-edit starter project for custom business logic

## Installation

### Prerequisites

- Python 3.10+
- Poetry
- PostgreSQL or SQLite for local development
- Redis optional for cache/keystore-backed auth flows

### Create the environment

```bash
cd fastapi-template
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
poetry install
```

If you are running inside a containerized or constrained environment, the project also includes:

```bash
./container-install.sh
```

### Configure environment variables

Copy the example configuration before running the app:

```bash
cp .env-example .env
```

Key values from the template include:

```env
PROJECT_NAME="Project Backend"
SECRET_KEY=your-super-secret-key
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=dbname
USE_SQLITE=false
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=xxxxxxxxxxxx
```

## Quickstart

### Run the API locally

```bash
poetry run uvicorn app.main:app --reload
```

The app exposes the API router at the configured `settings.API_V1_STR`, and the generated service includes the auth and account routers in `app/api/api_v1/api.py`.

### Health check

```bash
curl http://localhost:8000/api/v1/docs
```

## How the template is structured

```text
app/
├── api/
│   ├── api_v1/api.py
│   ├── deps.py
│   └── endpoints/
├── core/
│   └── config.py
├── db/
│   └── session.py
├── models/__init__.py
├── actions/__init__.py
├── main.py
├── bootstrap.py
└── tests/
```

The key pattern in this project is:

1. Define settings in `app.core.config`.
2. Build shared dependencies in `app.api.deps`.
3. Mount auth/account/workspace routers in `app.api.api_v1.api`.
4. Use `app.actions` for typed service operations.

## Typical integration pattern

```python
from app.core.config import settings
from app.api.deps import get_session, get_current_account
from msflib.auth.router import router as auth_router
from msflib.account.router import account_router

app.include_router(
    auth_router(
        get_session=get_session,
        get_keystore=get_keystore,
        get_current_account=get_current_account,
        account_type=Account,
        account_read_type=AccountRead,
        settings=settings,
        active_statuses=[AccountStatus.active, AccountStatus.online],
        prefix="",
        tags=["auth"],
    )
)
```

## Example workflows

### Create a user account

The template re-exports account and workspace models from `app.models` and uses typed action classes defined in `app.actions`.

```python
from app.actions import account_action, workspace_action

account = account_action.create(
    email="user@example.com",
    password="strong-password",
)
```

### Access a protected endpoint

```python
from fastapi import Depends
from app.api.deps import get_current_account

@app.get("/me")
def read_me(current_account=Depends(get_current_account)):
    return {"id": current_account.id, "email": current_account.email}
```

## Related pages

- [Core configuration](core.md)
- [Authentication](auth.md)
- [Account management](account.md)
- [Workspaces](workspaces.md)
- [Summary](SUMMARY.md)

## Local development and testing

```bash
poetry run pytest
```

The project also includes helper scripts such as:

```bash
./tests-start.sh
./run_seeder.sh
```

These are useful when validating application bootstrapping and seeding data in a fresh environment.
