#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
./cloudflare/scripts/build_web_preview.sh
node --test cloudflare/*.test.mjs
PREVIEW_REVISION="$(git -C "${ORGPORTAL_DIR:-../OrgPortal}" rev-parse --short HEAD)-$(date -u +%Y%m%dT%H%M%SZ)"
python3 cloudflare/scripts/with_cloudflare_env.py \
  npx wrangler deploy --config wrangler.preview.toml --var "PREVIEW_REVISION:$PREVIEW_REVISION"
