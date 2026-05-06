#!/usr/bin/env bash

set -e
set -x

PYTEST_XDIST_WORKERS="${PYTEST_XDIST_WORKERS:-auto}"

pytest -n "${PYTEST_XDIST_WORKERS}" --cov=app --cov-report=term-missing app/tests "${@}"
