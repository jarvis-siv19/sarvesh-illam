#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export SARVESH_CONFIG_DIR="$PWD/alerts"
export SARVESH_DATA_DIR="$PWD/data/home"
export HOME_API_PORT=8090
export PYTHONPATH="$PWD/alerts"

exec alerts/.venv/bin/python -m service.home_main >>data/home/home.log 2>&1
