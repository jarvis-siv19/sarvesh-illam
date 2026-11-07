#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

ALL=(dashboard home cctv alerts homeassistant)
HOST_HOME=false
if [ "$(uname -s)" = "Darwin" ]; then HOST_HOME=true; fi

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
  mkdir -p data/home data/alerts data/homeassistant .runtime
  if [ ! -f alerts/config.local.yaml ]; then
    printf '# Per-house devices. See config.local.example.yaml for a complete example.\nsmarteefi:\n  strips: []\n' > alerts/config.local.yaml
    echo "Created empty alerts/config.local.yaml — add this house's devices when ready."
  fi
  if [ ! -f data/homeassistant/configuration.yaml ]; then
    printf 'default_config:\n' > data/homeassistant/configuration.yaml
  fi
}

home_log_file="data/home/home.log"
home_launch_label="com.sarvesh-illam.home"

home_running() {
  launchctl print "gui/$(id -u)/$home_launch_label" >/dev/null 2>&1
}

start_host_home() {
  if home_running; then
    echo "Home bridge already running."
    return
  fi
  if [ ! -x alerts/.venv/bin/python ]; then
    python3 -m venv alerts/.venv
    alerts/.venv/bin/pip install -r alerts/requirements-home.txt
  fi
  launchctl remove "$home_launch_label" >/dev/null 2>&1 || true
  launchctl submit -l "$home_launch_label" -o /dev/null -e /dev/null -- \
    "$PWD/scripts/run-home-host.sh"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://127.0.0.1:8090/api/home/config >/dev/null 2>&1; then
      echo "Home bridge started."
      return
    fi
    sleep 1
  done
  echo "Home bridge did not become ready; see $home_log_file" >&2
  return 1
}

stop_host_home() {
  if ! home_running; then
    echo "Home bridge is not running."
    return
  fi
  launchctl remove "$home_launch_label"
  echo "Home bridge stopped."
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

docker_selected=()
home_selected=false
for service in "${selected[@]}"; do
  if $HOST_HOME && [ "$service" = "home" ]; then
    home_selected=true
  else
    docker_selected+=("$service")
  fi
done

case "$command" in
  start)
    prepare
    if [ "${#docker_selected[@]}" -gt 0 ]; then
      docker compose up -d --build "${docker_selected[@]}"
    fi
    if $home_selected; then
      docker compose rm -sf home >/dev/null 2>&1 || true
      start_host_home
    fi
    ;;
  stop)
    if [ "${#docker_selected[@]}" -gt 0 ]; then docker compose stop "${docker_selected[@]}"; fi
    if $home_selected; then stop_host_home; fi
    ;;
  restart)
    prepare
    if [ "${#docker_selected[@]}" -gt 0 ]; then
      docker compose up -d --build --force-recreate "${docker_selected[@]}"
    fi
    if $home_selected; then
      stop_host_home
      docker compose rm -sf home >/dev/null 2>&1 || true
      start_host_home
    fi
    ;;
  logs)
    if $home_selected && [ "${#docker_selected[@]}" -eq 0 ]; then
      tail -n 100 -f "$home_log_file"
    elif $home_selected; then
      tail -n 100 "$home_log_file"
    fi
    if [ "${#docker_selected[@]}" -gt 0 ]; then
      docker compose logs -f --tail=100 "${docker_selected[@]}"
    fi
    ;;
  status)
    docker compose ps -a
    if $HOST_HOME; then
      if home_running; then
        echo "home (host bridge): running"
      else
        echo "home (host bridge): stopped"
      fi
    fi
    ;;
  down)
    if $HOST_HOME; then stop_host_home; fi
    docker compose down
    ;;
  *) usage; exit 2 ;;
esac
