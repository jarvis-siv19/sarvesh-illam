#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

ALL=(dashboard home cctv alerts homeassistant)

usage() {
  cat <<'EOF'
Usage:
  ./stack.sh start [service ...]    default: dashboard home
  ./stack.sh stop [service ...]
  ./stack.sh restart [service ...]
  ./stack.sh logs [service ...]
  ./stack.sh status
  ./stack.sh down

Services: dashboard home cctv alerts homeassistant all
EOF
}

prepare() {
  mkdir -p data/home data/alerts data/homeassistant
  if [ ! -f alerts/config.local.yaml ]; then
    printf '# Per-house devices. See config.local.example.yaml for a complete example.\nsmarteefi:\n  strips: []\n' > alerts/config.local.yaml
    echo "Created empty alerts/config.local.yaml — add this house's devices when ready."
  fi
  if [ ! -f data/homeassistant/configuration.yaml ]; then
    printf 'default_config:\n' > data/homeassistant/configuration.yaml
  fi
}

services() {
  if [ "$#" -eq 0 ]; then
    printf '%s\n' dashboard home
  elif [ "$1" = "all" ]; then
    printf '%s\n' "${ALL[@]}"
  else
    printf '%s\n' "$@"
  fi
}

command="${1:-}"
if [ -z "$command" ]; then usage; exit 2; fi
shift || true
mapfile_supported=false
if help mapfile >/dev/null 2>&1; then mapfile_supported=true; fi
if $mapfile_supported; then
  mapfile -t selected < <(services "$@")
else
  selected=($(services "$@"))
fi

case "$command" in
  start)
    prepare
    docker compose up -d --build "${selected[@]}"
    ;;
  stop)
    docker compose stop "${selected[@]}"
    ;;
  restart)
    prepare
    docker compose up -d --build --force-recreate "${selected[@]}"
    ;;
  logs)
    docker compose logs -f --tail=100 "${selected[@]}"
    ;;
  status)
    docker compose ps -a
    ;;
  down)
    docker compose down
    ;;
  *) usage; exit 2 ;;
esac
