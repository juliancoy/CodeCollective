#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/portal/web"
LOCAL_DOCKER_DIR="$ROOT_DIR/.docker-local"
WEB_NODE_MODULES_DIR="$LOCAL_DOCKER_DIR/web-node_modules"
WEB_NPM_CACHE_DIR="$LOCAL_DOCKER_DIR/npm-cache"

NODE_IMAGE="${NODE_IMAGE:-node:24-alpine}"
CONTAINER_NAME="${CONTAINER_NAME:-codecollective-web-local}"
PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"
RESTART_POLICY="${RESTART_POLICY:-unless-stopped}"
ORGPORTAL_ORG_API_BASE="${ORGPORTAL_ORG_API_BASE:-https://codecollective.us/api/org}"
VITE_PIDP_BASE_URL="${VITE_PIDP_BASE_URL:-https://id.codecollective.us}"
VITE_PIDP_APP_SLUG="${VITE_PIDP_APP_SLUG:-code-collective}"
VITE_DATA_SOURCE="${VITE_DATA_SOURCE:-api}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-/api/governance}"
VITE_PUBLIC_BASE="${VITE_PUBLIC_BASE:-/}"

USER_ID="$(id -u)"
GROUP_ID="$(id -g)"
COMMAND="deploy"

usage() {
  cat <<'EOF'
Usage: ./deploy-local-docker.sh [command] [options]

Build and serve the portal web app locally using a generic Node Docker image
and a bind-mounted workspace volume. Docker is run as the current UID/GID so
generated files remain owned by the current user.

Commands:
  deploy, start          Build, replace, and start the local container (default)
  stop                   Stop and remove the local container
  restart                Restart the existing local container without rebuilding
  status                 Show container status
  logs                   Follow container logs

Options:
  --port <port>           Host/container port (default: 8080)
  --host <address>        Host bind address (default: 127.0.0.1)
  --name <name>           Docker container name (default: codecollective-web-local)
  --node-image <image>    Node image (default: node:24-alpine)
  --api-base <url>        Org API base for SSR metadata (default: https://codecollective.us/api/org)
  --restart <policy>      Docker restart policy (default: unless-stopped)
  --help                  Show this help

Environment overrides:
  PORT, HOST, CONTAINER_NAME, NODE_IMAGE, RESTART_POLICY,
  ORGPORTAL_ORG_API_BASE, VITE_PIDP_BASE_URL, VITE_PIDP_APP_SLUG,
  VITE_DATA_SOURCE, VITE_API_BASE_URL, VITE_PUBLIC_BASE

Examples:
  ./deploy-local-docker.sh
  ./deploy-local-docker.sh stop
  ./deploy-local-docker.sh restart
  ./deploy-local-docker.sh status
  ./deploy-local-docker.sh logs
  PORT=4175 ./deploy-local-docker.sh
  ./deploy-local-docker.sh --api-base http://host.docker.internal:8787
EOF
}

while (($#)); do
  case "$1" in
    deploy|start|stop|restart|status|logs)
      COMMAND="$1"
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --name)
      CONTAINER_NAME="$2"
      shift 2
      ;;
    --node-image)
      NODE_IMAGE="$2"
      shift 2
      ;;
    --api-base)
      ORGPORTAL_ORG_API_BASE="$2"
      shift 2
      ;;
    --restart)
      RESTART_POLICY="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[local-deploy] unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "[local-deploy] docker not found" >&2
  exit 1
fi

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"
}

require_web_app() {
  if [[ ! -f "$WEB_DIR/package.json" || ! -f "$WEB_DIR/server.mjs" ]]; then
    echo "[local-deploy] expected portal web app at $WEB_DIR" >&2
    exit 1
  fi
}

deploy_container() {
  require_web_app
  mkdir -p "$WEB_NODE_MODULES_DIR" "$WEB_NPM_CACHE_DIR"

  echo "[local-deploy] building portal web app with $NODE_IMAGE"
  docker run --rm \
    --user "$USER_ID:$GROUP_ID" \
    --workdir /workspace/portal/web \
    --volume "$ROOT_DIR:/workspace" \
    --volume "$WEB_NODE_MODULES_DIR:/workspace/portal/web/node_modules" \
    --volume "$WEB_NPM_CACHE_DIR:/tmp/.npm" \
    --env HOME=/tmp \
    --env VITE_PIDP_BASE_URL="$VITE_PIDP_BASE_URL" \
    --env VITE_PIDP_APP_SLUG="$VITE_PIDP_APP_SLUG" \
    --env VITE_DATA_SOURCE="$VITE_DATA_SOURCE" \
    --env VITE_API_BASE_URL="$VITE_API_BASE_URL" \
    --env VITE_PUBLIC_BASE="$VITE_PUBLIC_BASE" \
    "$NODE_IMAGE" \
    sh -lc 'npm ci && npm run build'

  if container_exists; then
    echo "[local-deploy] replacing existing container: $CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi

  echo "[local-deploy] starting $CONTAINER_NAME on http://$HOST:$PORT"
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart "$RESTART_POLICY" \
    --user "$USER_ID:$GROUP_ID" \
    --workdir /workspace/portal/web \
    --volume "$ROOT_DIR:/workspace" \
    --volume "$WEB_NODE_MODULES_DIR:/workspace/portal/web/node_modules" \
    --publish "$HOST:$PORT:$PORT" \
    --env HOME=/tmp \
    --env PORT="$PORT" \
    --env ORGPORTAL_ORG_API_BASE="$ORGPORTAL_ORG_API_BASE" \
    "$NODE_IMAGE" \
    node server.mjs

  echo "[local-deploy] running at http://$HOST:$PORT"
  echo "[local-deploy] restart policy: $RESTART_POLICY"
  echo "[local-deploy] stop with: $0 stop"
}

stop_container() {
  if ! container_exists; then
    echo "[local-deploy] container not found: $CONTAINER_NAME"
    return 0
  fi
  echo "[local-deploy] stopping and removing $CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null
}

restart_container() {
  if ! container_exists; then
    echo "[local-deploy] container not found: $CONTAINER_NAME" >&2
    echo "[local-deploy] run deploy first: $0 deploy" >&2
    exit 1
  fi
  echo "[local-deploy] restarting $CONTAINER_NAME"
  docker restart "$CONTAINER_NAME" >/dev/null
  echo "[local-deploy] running at http://$HOST:$PORT"
}

status_container() {
  if ! container_exists; then
    echo "[local-deploy] container not found: $CONTAINER_NAME"
    return 0
  fi
  docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
  echo "[local-deploy] restart policy: $(docker inspect "$CONTAINER_NAME" --format '{{.HostConfig.RestartPolicy.Name}}')"
  if container_running; then
    echo "[local-deploy] URL: http://$HOST:$PORT"
  fi
}

logs_container() {
  if ! container_exists; then
    echo "[local-deploy] container not found: $CONTAINER_NAME" >&2
    exit 1
  fi
  docker logs -f "$CONTAINER_NAME"
}

case "$COMMAND" in
  deploy|start)
    deploy_container
    ;;
  stop)
    stop_container
    ;;
  restart)
    restart_container
    ;;
  status)
    status_container
    ;;
  logs)
    logs_container
    ;;
esac
