#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.cloudflare}"
SKIP_BUILD=0
NO_VERIFY=0
TARGET="${TARGET:-both}"
VERBOSE=0

PROD_WORKER_NAME="${PROD_WORKER_NAME:-codecollective-site}"
DEV_WORKER_NAME="${DEV_WORKER_NAME:-codecollective-site-dev}"

PROD_GOVERNANCE_API_ORIGIN="${PROD_GOVERNANCE_API_ORIGIN:-https://portal.arkavo.org}"
PROD_PIDP_API_ORIGIN="${PROD_PIDP_API_ORIGIN:-https://id.codecollective.us}"
PROD_PIDP_PROXY_ORIGIN="${PROD_PIDP_PROXY_ORIGIN:-https://pidp-codecollective.jcloiacon.workers.dev}"
DEV_GOVERNANCE_API_ORIGIN="${DEV_GOVERNANCE_API_ORIGIN:-$PROD_GOVERNANCE_API_ORIGIN}"
DEV_PIDP_API_ORIGIN="${DEV_PIDP_API_ORIGIN:-$PROD_PIDP_API_ORIGIN}"
DEV_PIDP_PROXY_ORIGIN="${DEV_PIDP_PROXY_ORIGIN:-$PROD_PIDP_PROXY_ORIGIN}"

PASSTHROUGH_ARGS=()

usage() {
  cat <<'EOF'
Usage: ./deploy.sh [options] [-- <wrangler args>]

Options:
  --env-file <path>   Path to env file (default: ./.env.cloudflare)
  --target <value>    prod | dev | both (default: both)
  --verbose           Print full build/deploy logs
  STRICT_TS=1         Optional env: run strict TypeScript+Vite build during deploy
  --skip-build        Skip build_cloudflare_site.sh
  --no-verify         Skip post-deploy smoke checks
  -h, --help          Show this help

Examples:
  ./deploy.sh
  ./deploy.sh --target both
  ./deploy.sh --target dev
  ./deploy.sh --env-file .env.cloudflare
  DEV_PIDP_API_ORIGIN=https://id.codecollective.us ./deploy.sh --target dev
  DEV_PIDP_PROXY_ORIGIN=https://pidp-codecollective.jcloiacon.workers.dev ./deploy.sh --target dev
EOF
}

while (($#)); do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --target)
      TARGET="$2"
      shift 2
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --no-verify)
      NO_VERIFY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      PASSTHROUGH_ARGS+=("$@")
      break
      ;;
    *)
      PASSTHROUGH_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$TARGET" != "prod" && "$TARGET" != "dev" && "$TARGET" != "both" ]]; then
  echo "[deploy] invalid --target: $TARGET (expected prod|dev|both)" >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "[deploy] npx not found; install Node.js/npm first" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[deploy] curl not found" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
elif [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "[deploy] missing env file: $ENV_FILE" >&2
  echo "[deploy] set CLOUDFLARE_API_TOKEN or pass --env-file <path>" >&2
  exit 1
else
  echo "[deploy] env file not found; using exported Cloudflare environment"
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  echo "[deploy] building Cloudflare site bundle"
  if [[ "$VERBOSE" -eq 1 ]]; then
    VERBOSE_BUILD=1 "$ROOT_DIR/scripts/build_cloudflare_site.sh"
  else
    "$ROOT_DIR/scripts/build_cloudflare_site.sh"
  fi
fi

if [[ ! -f "$ROOT_DIR/.cloudflare/site/p/index.html" ]]; then
  echo "[deploy] portal entrypoint missing: .cloudflare/site/p/index.html" >&2
  echo "[deploy] deploy aborted" >&2
  exit 1
fi

echo "[deploy] deploying worker"
deploy_target() {
  local label="$1"
  local worker_name="$2"
  local governance_origin="$3"
  local pidp_origin="$4"
  local pidp_proxy_origin="$5"

  echo "[deploy][$label] deploying worker: $worker_name" >&2
  local deploy_log
  deploy_log="$(mktemp)"

  if [[ "$VERBOSE" -eq 1 ]]; then
    (
      cd "$ROOT_DIR"
      npx wrangler deploy \
        --name "$worker_name" \
        --var "GOVERNANCE_API_ORIGIN:$governance_origin" \
        --var "PIDP_API_ORIGIN:$pidp_origin" \
        --var "PIDP_PROXY_ORIGIN:$pidp_proxy_origin" \
        "${PASSTHROUGH_ARGS[@]}"
    ) 2>&1 | tee "$deploy_log" >&2
  else
    (
      cd "$ROOT_DIR"
      npx wrangler deploy \
        --name "$worker_name" \
        --var "GOVERNANCE_API_ORIGIN:$governance_origin" \
        --var "PIDP_API_ORIGIN:$pidp_origin" \
        --var "PIDP_PROXY_ORIGIN:$pidp_proxy_origin" \
        "${PASSTHROUGH_ARGS[@]}"
    ) 2>&1 \
      | tee "$deploy_log" \
      | awk '
          /^\+ \// { next }
          /Found [0-9]+ new or modified static assets to upload/ { print; next }
          /Uploaded [0-9]+ of [0-9]+ assets/ { print; next }
          /Success! Uploaded/ { print; next }
          /^Total Upload:/ { print; next }
          /^Uploaded .*workers.dev/ { print; next }
          /^Deployed .*triggers/ { print; next }
          /^  https:\/\/[A-Za-z0-9.-]+\.workers\.dev$/ { print; next }
          /^Current Version ID:/ { print; next }
        ' >&2
  fi

  local deployed_url
  deployed_url="$(rg -o 'https://[A-Za-z0-9.-]+\.workers\.dev' "$deploy_log" | tail -n 1 || true)"
  rm -f "$deploy_log"

  if [[ -z "$deployed_url" ]]; then
    deployed_url="https://${worker_name}.workers.dev"
  fi

  echo "$deployed_url"
}

verify_target() {
  local label="$1"
  local base_url="$2"
  echo "[deploy][$label] verifying $base_url"

  check() {
    local path="$1"
    local expect="$2"
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' -H 'Accept: text/html' "$base_url$path")"
    if [[ "$code" != "$expect" ]]; then
      echo "[deploy][$label] verify failed: $path returned $code (expected $expect)" >&2
      exit 1
    fi
    echo "[deploy][$label] ok: $path -> $code"
  }

  check "/" "200"
  check "/p/" "200"
  check "/p/constituent/dashboard" "200"
  check "/r8-rowhome/" "200"
}

DEV_URL=""
PROD_URL=""

if [[ "$TARGET" == "dev" || "$TARGET" == "both" ]]; then
  DEV_URL="$(deploy_target "dev" "$DEV_WORKER_NAME" "$DEV_GOVERNANCE_API_ORIGIN" "$DEV_PIDP_API_ORIGIN" "$DEV_PIDP_PROXY_ORIGIN")"
  echo "[deploy][dev] updated url: $DEV_URL"
fi

if [[ "$TARGET" == "prod" || "$TARGET" == "both" ]]; then
  PROD_URL="$(deploy_target "prod" "$PROD_WORKER_NAME" "$PROD_GOVERNANCE_API_ORIGIN" "$PROD_PIDP_API_ORIGIN" "$PROD_PIDP_PROXY_ORIGIN")"
  echo "[deploy][prod] updated url: $PROD_URL"
fi

if [[ "$NO_VERIFY" -eq 1 ]]; then
  echo "[deploy] done (verification skipped)"
  [[ -n "$DEV_URL" ]] && echo "[deploy] dev url:  $DEV_URL"
  [[ -n "$PROD_URL" ]] && echo "[deploy] prod url: $PROD_URL"
  exit 0
fi

[[ -n "$DEV_URL" ]] && verify_target "dev" "$DEV_URL"
[[ -n "$PROD_URL" ]] && verify_target "prod" "$PROD_URL"

echo "[deploy] complete"
if [[ -n "$DEV_URL" ]]; then
  echo "[deploy] dev url:  $DEV_URL"
fi
if [[ -n "$PROD_URL" ]]; then
  echo "[deploy] prod url: $PROD_URL"
fi
