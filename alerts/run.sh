#!/usr/bin/env bash
# Load ../.env (Telegram credentials) and start the alerts service via uv.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f ../.env ]; then
  set -a
  # shellcheck disable=SC1091
  source ../.env
  set +a
fi

exec uv run python -m service.main
