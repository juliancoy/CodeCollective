#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/.cloudflare/site"
PORTAL_WEB_DIR="$ROOT_DIR/portal/web"
MAX_ASSET_MB="${MAX_ASSET_MB:-25}"

echo "[cloudflare] preparing output directory: $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "[cloudflare] syncing legacy static site"
rsync -a \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.cloudflare/' \
  --exclude='portal/' \
  --exclude='portal_src/' \
  --exclude='cloudflare/' \
  --exclude='scripts/' \
  --exclude='usa/data/usajobs.json' \
  --exclude='usa/data/usajobs.json.gz' \
  --exclude='usa/data/usajobs-lite.json' \
  --exclude='usa/data/usajobs-lite.json.gz' \
  --exclude='usa/data/usajobs.zip' \
  --exclude='usa/data/publish/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='*.py' \
  --exclude='*.md' \
  --exclude='*.log' \
  --exclude='requirements.txt' \
  --exclude='package-lock.json' \
  --exclude='wrangler.toml' \
  "$ROOT_DIR/" "$OUT_DIR/"

echo "[cloudflare] building portal for /p/"
pushd "$PORTAL_WEB_DIR" >/dev/null
if ! VITE_PUBLIC_BASE=/p/ npm run build; then
  if [[ -d dist ]]; then
    echo "[cloudflare] warning: portal build failed; using existing portal/web/dist"
  else
    echo "[cloudflare] error: portal build failed and no dist/ found" >&2
    exit 1
  fi
fi
popd >/dev/null

echo "[cloudflare] syncing portal dist -> /p/"
mkdir -p "$OUT_DIR/p"
rsync -a --delete "$PORTAL_WEB_DIR/dist/" "$OUT_DIR/p/"

echo "[cloudflare] pruning files larger than ${MAX_ASSET_MB} MiB (Workers asset limit)"
if find "$OUT_DIR" -type f -size +"${MAX_ASSET_MB}"M -print -quit | grep -q .; then
  find "$OUT_DIR" -type f -size +"${MAX_ASSET_MB}"M -print -delete
fi

echo "[cloudflare] pruning files with non-URI-safe paths (Workers manifest requirement)"
python3 - "$OUT_DIR" <<'PY'
import os
import re
import sys

root = sys.argv[1]
safe = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/-]+$")
removed = 0

for dirpath, _, filenames in os.walk(root):
    for filename in filenames:
        path = os.path.join(dirpath, filename)
        rel = os.path.relpath(path, root)
        if not safe.match(rel):
            print(path)
            os.remove(path)
            removed += 1

print(f"[cloudflare] removed {removed} non-URI-safe files")
PY

echo "[cloudflare] done"
