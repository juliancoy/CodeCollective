#!/usr/bin/env python3
"""Version the shared navigation script by content, preserving its long cache TTL."""
import hashlib
from pathlib import Path
import re
import sys

def version_shared_header(directory):
    root = Path(directory)
    source = root / 'js/reusableComponents.js'
    if not source.is_file():
        raise SystemExit('Missing shared navigation script')
    version = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    pattern = re.compile(rb'''(\bsrc\s*=\s*["'])((?:/|(?:\.\./)*)js/reusableComponents\.js)(?:\?[^"']*)?(["'])''')
    count = 0
    for page in root.rglob('*.html'):
        original = page.read_bytes()
        updated = pattern.sub(lambda match: match[1] + match[2] + b'?v=' + version.encode('ascii') + match[3], original)
        if updated != original:
            page.write_bytes(updated)
            count += 1
    print(f'[cloudflare] shared header {version}: versioned {count} pages')

if __name__ == '__main__':
    version_shared_header(sys.argv[1])
