#!/usr/bin/env bash
set -e

# Let the DB start
python -m app.backend_pre_start

# Run migrations
alembic upgrade head

# Ensure required initial records exist without resetting existing tables/data.
python -m app.initial_data
