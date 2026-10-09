#!/usr/bin/env bash
set -e

python -m app.celeryworker_pre_start

celery -A app.worker:celery_app worker -l info -Q main-queue -c 1
