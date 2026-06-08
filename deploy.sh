#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.cloudflare}"
SKIP_BUILD=0
NO_VERIFY=0
TARGET="${TARGET:-both}"
COMPONENT="${COMPONENT:-all}"
VERBOSE=0
SKIP_PIDP_MIGRATIONS=0
DRY_RUN=0

PROD_WORKER_NAME="${PROD_WORKER_NAME:-codecollective-site}"
DEV_WORKER_NAME="${DEV_WORKER_NAME:-codecollective-site-dev}"
PIDP_DIR="$ROOT_DIR/portal/pidp/serverless"
ORG_WORKER_DIR="$ROOT_DIR/portal/org-worker"

ORG_WORKER_NAME="${ORG_WORKER_NAME:-org-codecollective}"
ORG_VERIFY_ORIGIN="${ORG_VERIFY_ORIGIN:-https://org-codecollective.jcloiacon.workers.dev}"
PROD_ORG_API_ORIGIN="${PROD_ORG_API_ORIGIN:-$ORG_VERIFY_ORIGIN}"
PROD_GOVERNANCE_API_ORIGIN="${PROD_GOVERNANCE_API_ORIGIN:-$PROD_ORG_API_ORIGIN}"
PROD_PIDP_API_ORIGIN="${PROD_PIDP_API_ORIGIN:-https://id.codecollective.us}"
PROD_PIDP_PROXY_ORIGIN="${PROD_PIDP_PROXY_ORIGIN:-https://pidp-codecollective.jcloiacon.workers.dev}"
DEV_GOVERNANCE_API_ORIGIN="${DEV_GOVERNANCE_API_ORIGIN:-$PROD_GOVERNANCE_API_ORIGIN}"
DEV_ORG_API_ORIGIN="${DEV_ORG_API_ORIGIN:-$PROD_ORG_API_ORIGIN}"
DEV_PIDP_API_ORIGIN="${DEV_PIDP_API_ORIGIN:-$PROD_PIDP_API_ORIGIN}"
DEV_PIDP_PROXY_ORIGIN="${DEV_PIDP_PROXY_ORIGIN:-$PROD_PIDP_PROXY_ORIGIN}"

PIDP_WORKER_NAME="${PIDP_WORKER_NAME:-pidp-codecollective}"
PIDP_APP_NAME="${PIDP_APP_NAME:-Code Collective ID}"
PIDP_ENV="${PIDP_ENV:-production}"
PIDP_ACCESS_TOKEN_EXPIRE_MINUTES="${PIDP_ACCESS_TOKEN_EXPIRE_MINUTES:-60}"
PIDP_ALLOWED_ORIGINS="${PIDP_ALLOWED_ORIGINS:-https://codecollective.us,https://www.codecollective.us}"
PIDP_ADMIN_EMAILS="${PIDP_ADMIN_EMAILS:-}"
PIDP_ADMIN_USER_IDS="${PIDP_ADMIN_USER_IDS:-}"
PIDP_PUBLIC_R2_BASE_URL="${PIDP_PUBLIC_R2_BASE_URL:-}"
PIDP_FRONTEND_REDIRECT_URL="${PIDP_FRONTEND_REDIRECT_URL:-https://codecollective.us/p/auth/callback}"
PIDP_GOOGLE_REDIRECT_URI="${PIDP_GOOGLE_REDIRECT_URI:-https://id.codecollective.us/auth/google/callback}"
PIDP_GITHUB_REDIRECT_URI="${PIDP_GITHUB_REDIRECT_URI:-https://id.codecollective.us/auth/github/callback}"
PIDP_D1_DATABASE_NAME="${PIDP_D1_DATABASE_NAME:-pidp}"
PIDP_D1_DATABASE_ID="${PIDP_D1_DATABASE_ID:-582fc740-4275-482a-bec0-a161a0aa6623}"
PIDP_R2_BUCKET_NAME="${PIDP_R2_BUCKET_NAME:-pidp-avatars}"
PIDP_VERIFY_ORIGIN="${PIDP_VERIFY_ORIGIN:-https://id.codecollective.us}"
ORG_PIDP_BASE_URL="${ORG_PIDP_BASE_URL:-https://id.codecollective.us}"
ORG_PUBLIC_PORTAL_BASE_URL="${ORG_PUBLIC_PORTAL_BASE_URL:-https://codecollective.us/p}"
ORG_ADMIN_EMAILS="${ORG_ADMIN_EMAILS:-$PIDP_ADMIN_EMAILS}"
ORG_ADMIN_USER_IDS="${ORG_ADMIN_USER_IDS:-$PIDP_ADMIN_USER_IDS}"
ORG_D1_DATABASE_NAME="${ORG_D1_DATABASE_NAME:-org}"
ORG_D1_DATABASE_ID="${ORG_D1_DATABASE_ID:-a71a2306-3d82-44cb-a50c-d7fdffaacdc7}"
SKIP_ORG_MIGRATIONS=0

PASSTHROUGH_ARGS=()

usage() {
  cat <<'EOF'
Usage: ./deploy.sh [options] [-- <wrangler args>]

Options:
  --env-file <path>   Path to env file (default: ./.env.cloudflare)
  --component <value>  all | site | pidp | org (default: all)
  --target <value>    prod | dev | both (default: both)
  --verbose           Print full build/deploy logs
  STRICT_TS=1         Optional env: run strict TypeScript+Vite build during deploy
  --skip-build        Skip build_cloudflare_site.sh
  --skip-pidp-migrations
                       Skip PIdP remote D1 migrations
  --skip-org-migrations
                       Skip org Worker remote D1 migrations
  --dry-run            Build and validate deploy commands without publishing
  --no-verify         Skip post-deploy smoke checks
  -h, --help          Show this help

Examples:
  ./deploy.sh
  ./deploy.sh --component all --target prod
  ./deploy.sh --component site --target dev
  ./deploy.sh --component pidp
  ./deploy.sh --component org
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
    --component)
      COMPONENT="$2"
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
    --skip-pidp-migrations)
      SKIP_PIDP_MIGRATIONS=1
      shift
      ;;
    --skip-org-migrations)
      SKIP_ORG_MIGRATIONS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ "$COMPONENT" != "all" && "$COMPONENT" != "site" && "$COMPONENT" != "pidp" && "$COMPONENT" != "org" ]]; then
  echo "[deploy] invalid --component: $COMPONENT (expected all|site|pidp|org)" >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "[deploy] npx not found; install Node.js/npm first" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[deploy] node not found; install Node.js first" >&2
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

deploy_site=0
deploy_pidp=0
deploy_org=0
if [[ "$COMPONENT" == "all" || "$COMPONENT" == "site" ]]; then
  deploy_site=1
fi
if [[ "$COMPONENT" == "all" || "$COMPONENT" == "pidp" ]]; then
  deploy_pidp=1
fi
if [[ "$COMPONENT" == "all" || "$COMPONENT" == "org" ]]; then
  deploy_org=1
fi

if [[ "$deploy_site" -eq 1 && "$SKIP_BUILD" -eq 0 ]]; then
  echo "[deploy] building Cloudflare site bundle"
  if [[ "$VERBOSE" -eq 1 ]]; then
    VERBOSE_BUILD=1 "$ROOT_DIR/scripts/build_cloudflare_site.sh"
  else
    "$ROOT_DIR/scripts/build_cloudflare_site.sh"
  fi
fi

if [[ "$deploy_site" -eq 1 && ! -f "$ROOT_DIR/.cloudflare/site/p/index.html" ]]; then
  echo "[deploy] portal entrypoint missing: .cloudflare/site/p/index.html" >&2
  echo "[deploy] deploy aborted" >&2
  exit 1
fi

write_pidp_config() {
  local required=(
    PIDP_WORKER_NAME
    PIDP_APP_NAME
    PIDP_ENV
    PIDP_ALLOWED_ORIGINS
    PIDP_FRONTEND_REDIRECT_URL
    PIDP_D1_DATABASE_NAME
    PIDP_D1_DATABASE_ID
    PIDP_R2_BUCKET_NAME
  )
  local missing=()
  for name in "${required[@]}"; do
    if [[ -z "${!name:-}" ]]; then
      missing+=("$name")
    fi
  done
  if [[ "${#missing[@]}" -gt 0 ]]; then
    echo "[deploy][pidp] missing required config: ${missing[*]}" >&2
    exit 1
  fi

  export PIDP_WORKER_NAME
  export PIDP_APP_NAME
  export PIDP_ENV
  export PIDP_ACCESS_TOKEN_EXPIRE_MINUTES
  export PIDP_ALLOWED_ORIGINS
  export PIDP_ADMIN_EMAILS
  export PIDP_ADMIN_USER_IDS
  export PIDP_PUBLIC_R2_BASE_URL
  export PIDP_FRONTEND_REDIRECT_URL
  export PIDP_GOOGLE_REDIRECT_URI
  export PIDP_GITHUB_REDIRECT_URI
  export PIDP_D1_DATABASE_NAME
  export PIDP_D1_DATABASE_ID
  export PIDP_R2_BUCKET_NAME

  (
    cd "$PIDP_DIR"
    node <<'NODE'
const fs = require("node:fs");

const env = process.env;
const config = {
  "$schema": "node_modules/wrangler/config-schema.json",
  name: env.PIDP_WORKER_NAME,
  main: "src/index.ts",
  compatibility_date: "2026-06-03",
  workers_dev: true,
  observability: { enabled: true },
  vars: {
    APP_NAME: env.PIDP_APP_NAME,
    ENV: env.PIDP_ENV,
    ACCESS_TOKEN_EXPIRE_MINUTES: env.PIDP_ACCESS_TOKEN_EXPIRE_MINUTES || "60",
    ALLOWED_ORIGINS: env.PIDP_ALLOWED_ORIGINS,
    ADMIN_EMAILS: env.PIDP_ADMIN_EMAILS || "",
    ADMIN_USER_IDS: env.PIDP_ADMIN_USER_IDS || "",
    PUBLIC_R2_BASE_URL: env.PIDP_PUBLIC_R2_BASE_URL || "",
    FRONTEND_REDIRECT_URL: env.PIDP_FRONTEND_REDIRECT_URL,
    GOOGLE_REDIRECT_URI: env.PIDP_GOOGLE_REDIRECT_URI || "",
    GITHUB_REDIRECT_URI: env.PIDP_GITHUB_REDIRECT_URI || "",
  },
  d1_databases: [
    {
      binding: "DB",
      database_name: env.PIDP_D1_DATABASE_NAME,
      database_id: env.PIDP_D1_DATABASE_ID,
    },
  ],
  r2_buckets: [
    {
      binding: "AVATARS",
      bucket_name: env.PIDP_R2_BUCKET_NAME,
    },
  ],
};

fs.writeFileSync("wrangler.jsonc", `${JSON.stringify(config, null, 2)}\n`);
NODE
  )
}

deploy_pidp_worker() {
  if [[ ! -d "$PIDP_DIR" ]]; then
    echo "[deploy][pidp] missing directory: $PIDP_DIR" >&2
    exit 1
  fi

  echo "[deploy][pidp] generating production Wrangler config"
  local config_path="$PIDP_DIR/wrangler.jsonc"
  local backup_path
  backup_path="$(mktemp)"
  cp "$config_path" "$backup_path"

  local args=()
  if [[ "$SKIP_PIDP_MIGRATIONS" -eq 1 ]]; then
    args+=("--skip-migrations")
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ "$SKIP_PIDP_MIGRATIONS" -eq 0 ]]; then
      args+=("--skip-migrations")
    fi
    args+=("--skip-status")
    args+=("--dry-run")
  fi
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    args+=("--skip-status")
  fi

  echo "[deploy][pidp] deploying Worker: $PIDP_WORKER_NAME"
  local status
  set +e
  write_pidp_config
  status=$?
  if [[ "$status" -eq 0 ]]; then
    if [[ "${GITHUB_ACTIONS:-}" == "true" || "${PIDP_USE_API_TOKEN:-0}" == "1" ]]; then
      (
        cd "$PIDP_DIR"
        npm run deploy:serverless -- "${args[@]}"
      )
    else
      echo "[deploy][pidp] using local Wrangler login; set PIDP_USE_API_TOKEN=1 to force CLOUDFLARE_API_TOKEN"
      (
        cd "$PIDP_DIR"
        env -u CLOUDFLARE_API_TOKEN npm run deploy:serverless -- "${args[@]}"
      )
    fi
    status=$?
  fi
  set -e
  cp "$backup_path" "$config_path"
  rm -f "$backup_path"
  return "$status"
}

write_org_config() {
  local required=(
    ORG_WORKER_NAME
    ORG_PIDP_BASE_URL
    ORG_PUBLIC_PORTAL_BASE_URL
    ORG_D1_DATABASE_NAME
    ORG_D1_DATABASE_ID
  )
  local missing=()
  for name in "${required[@]}"; do
    if [[ -z "${!name:-}" ]]; then
      missing+=("$name")
    fi
  done
  if [[ "${#missing[@]}" -gt 0 ]]; then
    echo "[deploy][org] missing required config: ${missing[*]}" >&2
    echo "[deploy][org] create D1 with: (cd portal/org-worker && npx wrangler d1 create org)" >&2
    exit 1
  fi

  export ORG_WORKER_NAME
  export ORG_PIDP_BASE_URL
  export ORG_PUBLIC_PORTAL_BASE_URL
  export ORG_ADMIN_EMAILS
  export ORG_ADMIN_USER_IDS
  export ORG_D1_DATABASE_NAME
  export ORG_D1_DATABASE_ID

  (
    cd "$ORG_WORKER_DIR"
    node <<'NODE'
const fs = require("node:fs");

const env = process.env;
const config = {
  "$schema": "node_modules/wrangler/config-schema.json",
  name: env.ORG_WORKER_NAME,
  main: "src/index.ts",
  compatibility_date: "2026-06-07",
  workers_dev: true,
  observability: { enabled: true },
  vars: {
    PIDP_BASE_URL: env.ORG_PIDP_BASE_URL,
    PUBLIC_PORTAL_BASE_URL: env.ORG_PUBLIC_PORTAL_BASE_URL,
    ADMIN_EMAILS: env.ORG_ADMIN_EMAILS || "",
    ADMIN_USER_IDS: env.ORG_ADMIN_USER_IDS || "",
  },
  d1_databases: [
    {
      binding: "DB",
      database_name: env.ORG_D1_DATABASE_NAME,
      database_id: env.ORG_D1_DATABASE_ID,
    },
  ],
};

fs.writeFileSync("wrangler.jsonc", `${JSON.stringify(config, null, 2)}\n`);
NODE
  )
}

deploy_org_worker() {
  if [[ ! -d "$ORG_WORKER_DIR" ]]; then
    echo "[deploy][org] missing directory: $ORG_WORKER_DIR" >&2
    exit 1
  fi

  echo "[deploy][org] generating production Wrangler config"
  local config_path="$ORG_WORKER_DIR/wrangler.jsonc"
  local backup_path
  backup_path="$(mktemp)"
  cp "$config_path" "$backup_path"

  local status
  set +e
  write_org_config
  status=$?
  if [[ "$status" -eq 0 ]]; then
    (
      cd "$ORG_WORKER_DIR"
      npm run typecheck
    )
    status=$?
  fi
  if [[ "$status" -eq 0 && "$SKIP_ORG_MIGRATIONS" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
    (
      cd "$ORG_WORKER_DIR"
      if [[ "${GITHUB_ACTIONS:-}" == "true" || "${ORG_USE_API_TOKEN:-0}" == "1" ]]; then
        npx wrangler d1 migrations apply "$ORG_D1_DATABASE_NAME" --remote
      else
        env -u CLOUDFLARE_API_TOKEN npx wrangler d1 migrations apply "$ORG_D1_DATABASE_NAME" --remote
      fi
    )
    status=$?
  fi
  if [[ "$status" -eq 0 ]]; then
    local wrangler_args=("${PASSTHROUGH_ARGS[@]}")
    if [[ "$DRY_RUN" -eq 1 ]]; then
      wrangler_args+=("--dry-run")
    fi
    if [[ "${GITHUB_ACTIONS:-}" == "true" || "${ORG_USE_API_TOKEN:-0}" == "1" ]]; then
      (
        cd "$ORG_WORKER_DIR"
        npx wrangler deploy "${wrangler_args[@]}"
      )
    else
      echo "[deploy][org] using local Wrangler login; set ORG_USE_API_TOKEN=1 to force CLOUDFLARE_API_TOKEN"
      (
        cd "$ORG_WORKER_DIR"
        env -u CLOUDFLARE_API_TOKEN npx wrangler deploy "${wrangler_args[@]}"
      )
    fi
    status=$?
  fi
  set -e
  cp "$backup_path" "$config_path"
  rm -f "$backup_path"
  return "$status"
}

deploy_target() {
  local label="$1"
  local worker_name="$2"
  local governance_origin="$3"
  local org_origin="$4"
  local pidp_origin="$5"
  local pidp_proxy_origin="$6"

  echo "[deploy][$label] deploying worker: $worker_name" >&2
  local deploy_log
  deploy_log="$(mktemp)"
  local wrangler_args=("${PASSTHROUGH_ARGS[@]}")
  if [[ "$DRY_RUN" -eq 1 ]]; then
    wrangler_args+=("--dry-run")
  fi

  if [[ "$VERBOSE" -eq 1 ]]; then
    (
      cd "$ROOT_DIR"
      npx wrangler deploy \
        --name "$worker_name" \
        --var "GOVERNANCE_API_ORIGIN:$governance_origin" \
        --var "ORG_API_ORIGIN:$org_origin" \
        --var "PIDP_API_ORIGIN:$pidp_origin" \
        --var "PIDP_PROXY_ORIGIN:$pidp_proxy_origin" \
        "${wrangler_args[@]}"
    ) 2>&1 | tee "$deploy_log" >&2
  else
    (
      cd "$ROOT_DIR"
      npx wrangler deploy \
        --name "$worker_name" \
        --var "GOVERNANCE_API_ORIGIN:$governance_origin" \
        --var "ORG_API_ORIGIN:$org_origin" \
        --var "PIDP_API_ORIGIN:$pidp_origin" \
        --var "PIDP_PROXY_ORIGIN:$pidp_proxy_origin" \
        "${wrangler_args[@]}"
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
  deployed_url="$(grep -Eo 'https://[A-Za-z0-9.-]+\.workers\.dev' "$deploy_log" | tail -n 1 || true)"
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

if [[ "$deploy_pidp" -eq 1 ]]; then
  deploy_pidp_worker
fi

if [[ "$deploy_org" -eq 1 ]]; then
  deploy_org_worker
fi

if [[ "$deploy_site" -eq 1 && ( "$TARGET" == "dev" || "$TARGET" == "both" ) ]]; then
  DEV_URL="$(deploy_target "dev" "$DEV_WORKER_NAME" "$DEV_GOVERNANCE_API_ORIGIN" "$DEV_ORG_API_ORIGIN" "$DEV_PIDP_API_ORIGIN" "$DEV_PIDP_PROXY_ORIGIN")"
  echo "[deploy][dev] updated url: $DEV_URL"
fi

if [[ "$deploy_site" -eq 1 && ( "$TARGET" == "prod" || "$TARGET" == "both" ) ]]; then
  PROD_URL="$(deploy_target "prod" "$PROD_WORKER_NAME" "$PROD_GOVERNANCE_API_ORIGIN" "$PROD_ORG_API_ORIGIN" "$PROD_PIDP_API_ORIGIN" "$PROD_PIDP_PROXY_ORIGIN")"
  echo "[deploy][prod] updated url: $PROD_URL"
fi

if [[ "$NO_VERIFY" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[deploy] done (dry-run; verification skipped)"
  else
    echo "[deploy] done (verification skipped)"
  fi
  [[ "$deploy_pidp" -eq 1 ]] && echo "[deploy] pidp url: $PIDP_VERIFY_ORIGIN"
  [[ "$deploy_org" -eq 1 ]] && echo "[deploy] org url:  $ORG_VERIFY_ORIGIN"
  [[ -n "$DEV_URL" ]] && echo "[deploy] dev url:  $DEV_URL"
  [[ -n "$PROD_URL" ]] && echo "[deploy] prod url: $PROD_URL"
  exit 0
fi

if [[ "$deploy_pidp" -eq 1 ]]; then
  echo "[deploy][pidp] verifying $PIDP_VERIFY_ORIGIN"
  pidp_code="$(curl -sS -o /dev/null -w '%{http_code}' "$PIDP_VERIFY_ORIGIN/health")"
  if [[ "$pidp_code" != "200" ]]; then
    echo "[deploy][pidp] verify failed: /health returned $pidp_code (expected 200)" >&2
    exit 1
  fi
  echo "[deploy][pidp] ok: /health -> 200"
fi

if [[ "$deploy_org" -eq 1 ]]; then
  echo "[deploy][org] verifying $ORG_VERIFY_ORIGIN"
  org_code="$(curl -sS -o /dev/null -w '%{http_code}' "$ORG_VERIFY_ORIGIN/health")"
  if [[ "$org_code" != "200" ]]; then
    echo "[deploy][org] verify failed: /health returned $org_code (expected 200)" >&2
    exit 1
  fi
  echo "[deploy][org] ok: /health -> 200"
fi

[[ -n "$DEV_URL" ]] && verify_target "dev" "$DEV_URL"
[[ -n "$PROD_URL" ]] && verify_target "prod" "$PROD_URL"

echo "[deploy] complete"
if [[ "$deploy_pidp" -eq 1 ]]; then
  echo "[deploy] pidp url: $PIDP_VERIFY_ORIGIN"
fi
if [[ "$deploy_org" -eq 1 ]]; then
  echo "[deploy] org url:  $ORG_VERIFY_ORIGIN"
fi
if [[ -n "$DEV_URL" ]]; then
  echo "[deploy] dev url:  $DEV_URL"
fi
if [[ -n "$PROD_URL" ]]; then
  echo "[deploy] prod url: $PROD_URL"
fi
