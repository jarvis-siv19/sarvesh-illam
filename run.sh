#!/usr/bin/env bash
# Load .env and start go2rtc. go2rtc expands ${VAR} in go2rtc.yaml from the
# environment, so credentials stay out of the committed config.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "error: .env not found. Run: cp .env.example .env  (then fill it in)" >&2
  exit 1
fi

if [ ! -x ./go2rtc ]; then
  echo "error: ./go2rtc binary not found. See README.md for the download step." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

for var in DVR_USER DVR_PASS DVR1_HOST DVR2_HOST; do
  if [ -z "${!var:-}" ]; then
    echo "error: $var is unset or empty in .env" >&2
    exit 1
  fi
done

exec ./go2rtc -config go2rtc.yaml
