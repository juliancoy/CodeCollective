#!/usr/bin/env python3
"""Run a command with existing Cloudflare deployment credentials; never print them."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
path = Path(os.environ.get('CLOUDFLARE_ENV_FILE', root / '.env.cloudflare'))
if path.exists():
    for line in path.read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        key = key.strip().removeprefix('export ')
        if key in ('CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_TOKEN'):
            os.environ.setdefault(key, value.strip().strip('\"\''))
if not os.environ.get('CLOUDFLARE_ACCOUNT_ID') or not os.environ.get('CLOUDFLARE_API_TOKEN'):
    raise SystemExit('Cloudflare account ID and API token are required in .env.cloudflare or the environment.')
if len(sys.argv) < 2:
    raise SystemExit('Pass the deployment command as arguments.')
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
