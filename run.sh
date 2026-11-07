#!/usr/bin/env bash
# Backwards-compatible minimal start: dashboard + local home devices only.
set -euo pipefail
exec "$(dirname "$0")/stack.sh" start dashboard home
