#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/calendar-next-app"
if [[ ! -d "$APP_DIR/node_modules" ]]; then
  npm ci --prefix "$APP_DIR"
fi
VITE_BASE=/calendar-next/ npm --prefix "$APP_DIR" run build
mkdir -p "$ROOT_DIR/calendar-next"
rsync -a --delete "$APP_DIR/dist/" "$ROOT_DIR/calendar-next/"
