#! /usr/bin/env bash
set -e

mkdir -p ./tmp

python -m app.tests_pre_start

bash ./scripts/test.sh "$@"

rm -rf ./tmp
