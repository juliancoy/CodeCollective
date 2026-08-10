#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELENIUM_IMAGE="${SELENIUM_IMAGE:-selenium/standalone-chrome:latest}"
SELENIUM_CONTAINER_NAME="${SELENIUM_CONTAINER_NAME:-codecollective-datacenters-selenium}"
SITE_PORT="${SITE_PORT:-8765}"
SITE_CONTAINER_NAME="${SITE_CONTAINER_NAME:-codecollective-local-site}"
SELENIUM_PORT="${SELENIUM_PORT:-4444}"
SELENIUM_URL="${SELENIUM_URL:-http://127.0.0.1:${SELENIUM_PORT}/wd/hub}"
DATACENTERS_BASE_URL="${DATACENTERS_BASE_URL:-https://host.docker.internal:${SITE_PORT}/datacenters.html}"
STARTED_SITE=0
STARTED_SELENIUM=0

cleanup() {
  if [[ "$STARTED_SELENIUM" == "1" ]]; then
    docker rm -f "$SELENIUM_CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
  if [[ "$STARTED_SITE" == "1" ]]; then
    "$ROOT_DIR/serve_local.sh" --clean >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

canonical_site_running() {
  local published
  published="$(docker ps \
    --filter "name=^/${SITE_CONTAINER_NAME}$" \
    --format '{{.Names}} {{.Ports}}')"
  [[ -n "$published" && ( "$published" == *"0.0.0.0:${SITE_PORT}->8080/tcp"* || "$published" == *"[::]:${SITE_PORT}->8080/tcp"* ) ]]
}

port_in_use() {
  python3 - "$SITE_PORT" <<'PY' >/dev/null 2>&1
import socket
import sys

sock = socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1)
sock.close()
PY
}

wait_for_http() {
  local url="$1"
  local label="$2"
  for _ in $(seq 1 80); do
    if python3 - "$url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request
import ssl

context = ssl._create_unverified_context()
with urllib.request.urlopen(sys.argv[1], timeout=2, context=context) as response:
    if response.status >= 400:
        raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 1
  done
  echo "[selenium-datacenters] timed out waiting for $label at $url" >&2
  return 1
}

wait_for_selenium() {
  local status_url="http://127.0.0.1:${SELENIUM_PORT}/status"
  for _ in $(seq 1 80); do
    if python3 - "$status_url" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
value = payload.get("value", {})
nodes = value.get("nodes") or []
has_up_node = any(node.get("availability") == "UP" for node in nodes)
if not (value.get("ready") or has_up_node):
    raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 1
  done
  echo "[selenium-datacenters] timed out waiting for Selenium at $SELENIUM_URL" >&2
  return 1
}

if ! command -v docker >/dev/null 2>&1; then
  echo "[selenium-datacenters] docker not found; install Docker first" >&2
  exit 1
fi

if ! canonical_site_running; then
  if port_in_use; then
    if docker ps --filter "name=^/${SITE_CONTAINER_NAME}$" --format '{{.Names}}' | grep -qx "$SITE_CONTAINER_NAME"; then
      echo "[selenium-datacenters] restarting ${SITE_CONTAINER_NAME} on 0.0.0.0:${SITE_PORT}" >&2
      "$ROOT_DIR/serve_local.sh" --clean >/dev/null 2>&1 || true
    else
      echo "[selenium-datacenters] port ${SITE_PORT} is occupied by a non-canonical server" >&2
      echo "[selenium-datacenters] expected Docker container ${SITE_CONTAINER_NAME} via serve_local.sh on 0.0.0.0:${SITE_PORT}" >&2
      exit 1
    fi
  fi
  echo "[selenium-datacenters] starting local site on 0.0.0.0:${SITE_PORT}"
  HOST=0.0.0.0 PORT="$SITE_PORT" "$ROOT_DIR/serve_local.sh" --detach
  STARTED_SITE=1
fi

wait_for_http "https://127.0.0.1:${SITE_PORT}/datacenters.html" "datacenters page"

if ! python3 - "$SELENIUM_PORT" <<'PY' >/dev/null 2>&1
import socket
import sys

sock = socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1)
sock.close()
PY
then
  echo "[selenium-datacenters] starting ${SELENIUM_IMAGE}"
  docker rm -f "$SELENIUM_CONTAINER_NAME" >/dev/null 2>&1 || true
  docker run -d \
    --name "$SELENIUM_CONTAINER_NAME" \
    --shm-size=2g \
    --add-host=host.docker.internal:host-gateway \
    -e SE_NODE_MAX_SESSIONS=1 \
    -e SE_NODE_OVERRIDE_MAX_SESSIONS=true \
    -p "${SELENIUM_PORT}:4444" \
    "$SELENIUM_IMAGE" >/dev/null
  STARTED_SELENIUM=1
fi

wait_for_selenium

echo "[selenium-datacenters] base url: ${DATACENTERS_BASE_URL}"
SELENIUM_URL="$SELENIUM_URL" DATACENTERS_BASE_URL="$DATACENTERS_BASE_URL" \
  python3 "$ROOT_DIR/datacenters/scripts/selenium-datacenters-smoke.py" "$@"
