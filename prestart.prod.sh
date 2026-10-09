#!/usr/bin/env bash
# Production bootstrap for empty Postgres:
# msflib base tables come from SQLModel metadata; SocialChef alembic revisions
# assume those already exist. On a fresh DB we create_all + stamp; otherwise upgrade.
set -e

python -m app.backend_pre_start

python - <<'PY'
from sqlalchemy import inspect
from sqlmodel import SQLModel

from app import models  # noqa: F401 — register metadata
from app.db.session import engine

inspector = inspect(engine)
existing = {name.lower() for name in inspector.get_table_names()}
if "workspace" not in existing:
    print("Fresh database detected — creating schema from SQLModel metadata")
    SQLModel.metadata.create_all(engine)
    open("/tmp/socialchef_stamp_alembic", "w").write("1")
else:
    print("Existing schema detected — will run alembic upgrade")
PY

if [[ -f /tmp/socialchef_stamp_alembic ]]; then
  rm -f /tmp/socialchef_stamp_alembic
  alembic stamp head
else
  alembic upgrade head
fi

python -m app.initial_data
