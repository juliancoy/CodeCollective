#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/.cloudflare/site"
PORTAL_WEB_DIR="$ROOT_DIR/portal/web"
MAX_ASSET_MB="${MAX_ASSET_MB:-25}"
VERBOSE_BUILD="${VERBOSE_BUILD:-0}"
STRICT_TS="${STRICT_TS:-0}"

echo "[cloudflare] preparing output directory: $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "[cloudflare] syncing legacy static site"
rsync -a \
  --exclude='.git/' \
  --exclude='.wrangler/' \
  --exclude='.codex' \
  --exclude='.codexignore' \
  --exclude='.clineignore' \
  --exclude='.env*' \
  --exclude='**/.gitignore' \
  --exclude='.github/' \
  --exclude='.cloudflare/' \
  --exclude='portal/' \
  --exclude='portal_src/' \
  --exclude='r8-rowhome/' \
  --exclude='cloudflare/' \
  --exclude='scripts/' \
  --exclude='usa/data/usajobs.json' \
  --exclude='usa/data/usajobs.json.gz' \
  --exclude='usa/data/usajobs-lite.json' \
  --exclude='usa/data/usajobs-lite.json.gz' \
  --exclude='usa/data/usajobs.zip' \
  --exclude='usa/data/publish/' \
  --exclude='baltimore/data/vacants.geojson' \
  --exclude='baltimore/data/vacants.geojson.gz' \
  --exclude='baltimore/data/publish/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite-shm' \
  --exclude='*.sqlite-wal' \
  --exclude='*.db' \
  --exclude='*.py' \
  --exclude='*.md' \
  --exclude='*.log' \
  --exclude='requirements.txt' \
  --exclude='package-lock.json' \
  --exclude='wrangler.toml' \
  "$ROOT_DIR/" "$OUT_DIR/"

echo "[cloudflare] building portal for /p/"
pushd "$PORTAL_WEB_DIR" >/dev/null
if [[ "$STRICT_TS" == "1" ]]; then
  echo "[cloudflare] strict mode: running TypeScript + Vite build"
  VITE_PUBLIC_BASE=/p/ npm run build
else
  echo "[cloudflare] deploy mode: running Vite build (TypeScript checks run separately in CI)"
  VITE_PUBLIC_BASE=/p/ npx vite build
fi
popd >/dev/null

if [[ ! -f "$PORTAL_WEB_DIR/dist/index.html" ]]; then
  echo "[cloudflare] error: expected portal/web/dist/index.html after build" >&2
  exit 1
fi

echo "[cloudflare] syncing portal dist -> /p/"
mkdir -p "$OUT_DIR/p"
rsync -a --delete "$PORTAL_WEB_DIR/dist/" "$OUT_DIR/p/"

echo "[cloudflare] building r8-rowhome for /r8-rowhome/"
R8_ROWHOME_DIR="$ROOT_DIR/r8-rowhome"
if [[ -d "$R8_ROWHOME_DIR" ]]; then
  pushd "$R8_ROWHOME_DIR" >/dev/null
  if [[ "$STRICT_TS" == "1" ]]; then
    echo "[cloudflare] strict mode: running TypeScript + Vite build for r8-rowhome"
    VITE_PUBLIC_BASE=/r8-rowhome/ npm run build
  else
    echo "[cloudflare] deploy mode: running Vite build for r8-rowhome"
    VITE_PUBLIC_BASE=/r8-rowhome/ npx vite build
  fi
  popd >/dev/null

  if [[ ! -f "$R8_ROWHOME_DIR/dist/index.html" ]]; then
    echo "[cloudflare] error: expected r8-rowhome/dist/index.html after build" >&2
    exit 1
  fi

  echo "[cloudflare] syncing r8-rowhome dist -> /r8-rowhome/"
  mkdir -p "$OUT_DIR/r8-rowhome"
  rsync -a --delete "$R8_ROWHOME_DIR/dist/" "$OUT_DIR/r8-rowhome/"
else
  echo "[cloudflare] warning: r8-rowhome directory not found, skipping"
fi

echo "[cloudflare] pruning files larger than ${MAX_ASSET_MB} MiB (Workers asset limit)"
if find "$OUT_DIR" -type f -size +"${MAX_ASSET_MB}"M -print -quit | grep -q .; then
  if [[ "$VERBOSE_BUILD" == "1" ]]; then
    find "$OUT_DIR" -type f -size +"${MAX_ASSET_MB}"M -print -delete
  else
    LARGE_COUNT="$(find "$OUT_DIR" -type f -size +"${MAX_ASSET_MB}"M | wc -l | tr -d ' ')"
    find "$OUT_DIR" -type f -size +"${MAX_ASSET_MB}"M -delete
    echo "[cloudflare] removed ${LARGE_COUNT} oversized files"
  fi
fi

echo "[cloudflare] pruning files with non-URI-safe paths (Workers manifest requirement)"
VERBOSE_BUILD="$VERBOSE_BUILD" python3 - "$OUT_DIR" <<'PY'
import os
import re
import sys

root = sys.argv[1]
safe = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/-]+$")
verbose = os.getenv("VERBOSE_BUILD", "0") == "1"
removed = 0

for dirpath, _, filenames in os.walk(root):
    for filename in filenames:
        path = os.path.join(dirpath, filename)
        rel = os.path.relpath(path, root)
        if not safe.match(rel):
            if verbose:
                print(path)
            os.remove(path)
            removed += 1

print(f"[cloudflare] removed {removed} non-URI-safe files")
PY

echo "[cloudflare] writing static cache headers"
cat > "$OUT_DIR/_headers" <<'EOF'
/*
  Cache-Control: public, max-age=300

/p/assets/*
  Cache-Control: public, max-age=31536000, immutable

/r8-rowhome/assets/*
  Cache-Control: public, max-age=31536000, immutable

/images/*
  Cache-Control: public, max-age=2592000

/css/*
  Cache-Control: public, max-age=2592000

/js/*
  Cache-Control: public, max-age=2592000

/audio/*
  Cache-Control: public, max-age=2592000

/videos/*
  Cache-Control: public, max-age=2592000
EOF

echo "[cloudflare] done"
