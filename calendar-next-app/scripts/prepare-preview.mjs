/**
 * Builds the hosted preview bundle.
 *
 * Differences from `npm run build`:
 *  - relative asset URLs, so it can sit at any path
 *  - the concept banner, so a viewer is never left thinking this is the live
 *    Code Collective site
 *  - a minified snapshot shipped alongside, and the snapshot fallback enabled.
 *    A sandboxed frame cannot always reach codecollective.us, and an error
 *    state is a poor thing to hand someone you asked to look at a redesign.
 *    The app still tries the live feed first and says which one it got.
 *  - any literal U+FFFD in the emitted JavaScript is rewritten to its escape
 *    sequence. `marked` ships one as its invalid-code-point fallback, and some
 *    static hosts reject that byte as corruption. The escape is the identical
 *    character to the JavaScript engine.
 *
 * Usage: npm run build:preview
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const OUT = 'dist-artifact';
const SNAPSHOT_DATE = '25 September 2026';

/** U+FFFD, and the six-character escape that means the same thing. */
const RAW = String.fromCharCode(0xfffd);
const ESCAPED = String.fromCharCode(92) + 'uFFFD';

fs.rmSync(OUT, { recursive: true, force: true });

execFileSync('npx', ['vite', 'build', '--outDir', OUT], {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: {
    ...process.env,
    VITE_BASE: './',
    VITE_DEMO_NOTE: '1',
    VITE_SNAPSHOT_FALLBACK: '1',
    VITE_SNAPSHOT_DATE: SNAPSHOT_DATE,
  },
});

// Vite copies public/ verbatim. The snapshot is pretty-printed in the repo,
// which is 21% of its bytes for no benefit over the wire.
const snapshotPath = path.join(OUT, 'snapshot', 'baltimore.json');
const pretty = fs.readFileSync(snapshotPath, 'utf8');
const minified = JSON.stringify(JSON.parse(pretty));
fs.writeFileSync(snapshotPath, minified, 'utf8');

let patched = 0;
const assets = path.join(OUT, 'assets');
for (const name of fs.readdirSync(assets)) {
  if (!name.endsWith('.js')) continue;
  const file = path.join(assets, name);
  const source = fs.readFileSync(file, 'utf8');
  if (!source.includes(RAW)) continue;
  fs.writeFileSync(file, source.split(RAW).join(ESCAPED), 'utf8');
  patched++;
}

// Fail loudly rather than shipping something the host will reject.
for (const name of fs.readdirSync(assets)) {
  if (!/\.(js|css)$/.test(name)) continue;
  const source = fs.readFileSync(path.join(assets, name), 'utf8');
  if (source.includes(RAW)) throw new Error(`${name} still contains a literal U+FFFD`);
}

const kb = (n) => `${Math.round(n / 1024)} KB`;
console.log(
  `\nprepare-preview: ${fs.readdirSync(assets).length + 2} files in ${OUT}` +
    `, ${patched} escaped for U+FFFD` +
    `, snapshot ${kb(pretty.length)} -> ${kb(minified.length)}`,
);
