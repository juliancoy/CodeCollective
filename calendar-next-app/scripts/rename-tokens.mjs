/**
 * One-off: rename the v1 design tokens to their v2 names across the source.
 * Kept in the repo so the mapping is auditable rather than a mystery diff.
 */
import fs from 'node:fs';
import path from 'node:path';

const MAP = [
  ['var(--surface-2)', 'var(--bg-soft)'],
  ['var(--surface)', 'var(--bg)'],
  ['var(--accent-soft)', 'var(--brand-soft)'],
  ['var(--accent-ink)', 'var(--brand-ink)'],
  ['var(--accent)', 'var(--brand)'],
  ['t-display', 't-h1'],
];

let changed = 0;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(p);
      continue;
    }
    if (!/\.(tsx?|css)$/.test(entry.name)) continue;
    if (/\.test\.ts$/.test(entry.name)) continue;

    const before = fs.readFileSync(p, 'utf8');
    let after = before;
    for (const [from, to] of MAP) after = after.split(from).join(to);
    if (after !== before) {
      fs.writeFileSync(p, after, 'utf8');
      changed++;
      console.log('updated', p);
    }
  }
}

walk('src');
console.log(`\n${changed} files updated`);
