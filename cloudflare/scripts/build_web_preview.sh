#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIFETECH_DIR="${LIFETECH_DIR:-$ROOT_DIR/../BmoreMedTech}"
ORGPORTAL_DIR="${ORGPORTAL_DIR:-$ROOT_DIR/../OrgPortal}"
# Reuse the supported shared frontend build. Keep preview assets in a separate output directory.
"$ROOT_DIR/cloudflare/scripts/build_cloudflare_site.sh"
npm --prefix "$LIFETECH_DIR" run build:lifetech
mkdir -p "$ROOT_DIR/.cloudflare/preview"
rsync -a --delete "$LIFETECH_DIR/dist-lifetech/" "$ROOT_DIR/.cloudflare/preview/"
rsync -a "$ROOT_DIR/.cloudflare/site/p/" "$ROOT_DIR/.cloudflare/preview/p/"
rsync -a "$ROOT_DIR/.cloudflare/site/__portal_root/" "$ROOT_DIR/.cloudflare/preview/__portal_root/"
node - "$ROOT_DIR/.cloudflare/preview" <<'JS'
const fs = require('node:fs');
const output = process.argv[2];
fs.writeFileSync(`${output}/robots.txt`, 'User-agent: *\nDisallow: /\n');
// Preview can never offer a production Android release.
for (const mount of ['p', '__portal_root']) {
  const path = `${output}/${mount}/mobile-update.json`;
  const manifest = JSON.parse(fs.readFileSync(path, 'utf8'));
  delete manifest.android;
  fs.writeFileSync(path, JSON.stringify(manifest, null, 2));
}
JS
