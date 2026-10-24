const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { gzipSync } = require('node:zlib');
const { chromium } = require(require.resolve('playwright', { paths: [
  '/work/.test-deps/usajobs', path.resolve(__dirname, '../../OrgPortal/web'),
] }));
const root = path.resolve(__dirname, '..');
const latest = 'v20260501T120000Z', archive = 'v20260424T173211Z';
let folder, server, browser, origin;

before(async () => {
  folder = fs.mkdtempSync(path.join(os.tmpdir(), 'usajobs-mobile-'));
  fs.mkdirSync(path.join(folder, 'usa'), { recursive: true });
  for (const file of ['index.html', 'jobs.js']) fs.copyFileSync(path.join(root, 'usa', file), path.join(folder, 'usa', file));
  fs.cpSync(path.join(root, 'css'), path.join(folder, 'css'), { recursive: true });
  for (const version of [latest, archive]) {
    const key = `jobs/${version}/shards/state=ALL/page=0001.json.gz`;
    const records = Array.from({ length: 80 }, (_, i) => ({ job_id: String(700000 + i),
      title: `${version === latest ? 'Current' : 'Historic'} example position ${i} with a long title`,
      agency: 'Example public agency', organization_name: 'Example public agency',
      status: 'Open', close_date: '2030-12-31T12:00:00Z', publication_date: '2026-04-24T12:00:00Z',
      position_id: `EXAMPLE-${i}`, locations: ['Baltimore, Maryland'], categories: ['Engineering'] }));
    const base = path.join(folder, 'usa/data/publish');
    fs.mkdirSync(path.dirname(path.join(base, key)), { recursive: true });
    fs.writeFileSync(path.join(base, key), gzipSync(JSON.stringify({ version, records })));
    fs.writeFileSync(path.join(base, `jobs/${version}/manifest.json`), JSON.stringify({ version,
      source_fetched_at: version === latest ? '2026-05-01T12:00:00Z' : '2026-04-24T17:31:43Z',
      source_record_count: records.length, states: { ALL: { shards: [{ page: 1, record_count: records.length, key }] } } }));
  }
  fs.writeFileSync(path.join(folder, 'usa/data/publish/jobs/latest.json'), JSON.stringify({ version: latest }));
  const python = `import functools,importlib.util,sys
from http.server import ThreadingHTTPServer
spec=importlib.util.spec_from_file_location('site_runner',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(module.LocalSiteHandler,directory=sys.argv[2]))
print(server.server_port,flush=True)
server.serve_forever()`;
  server = spawn('python3', ['-c', python, path.join(root, 'run.py'), folder], { stdio: ['ignore', 'pipe', 'pipe'] });
  server.stderr.on('data', () => {});
  const port = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(Error('Local fixture server did not start')), 10000);
    server.once('error', reject);
    server.once('exit', code => { clearTimeout(timeout); reject(Error(`Fixture server exited: ${code}`)); });
    server.stdout.once('data', bytes => { clearTimeout(timeout); resolve(Number(String(bytes).trim())); });
  });
  origin = `http://127.0.0.1:${port}`;
  browser = await chromium.launch({ headless: true });
});

after(async () => {
  if (browser) await browser.close();
  if (server) {
    const exited = new Promise(resolve => server.once('exit', resolve));
    server.kill(); await exited;
  }
  if (folder) fs.rmSync(folder, { recursive: true, force: true });
});

for (const [width, height] of [[360, 800], [390, 844], [412, 915], [844, 390], [1280, 900]]) {
  test(`USAJOBS remains browsable at ${width}x${height}`, { timeout: 60000 }, async () => {
    const context = await browser.newContext({ viewport: { width, height }, hasTouch: true });
    await context.route('**/*', route => {
      const url = route.request().url();
      if (url.startsWith(origin)) return route.continue();
      if (url.startsWith('https://www.usajobs.gov/job/')) return route.fulfill({ body: 'Official destination fixture', contentType: 'text/html' });
      return route.abort();
    });
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    try {
      await page.goto(origin + '/usa/', { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => !document.querySelector('#snapshot-select').disabled);
      const geometry = await page.locator('.bills-table-wrap').evaluate(n => ({ height: n.clientHeight, scroll: n.scrollHeight }));
      assert.ok(geometry.height >= 200, `Job list collapsed: ${JSON.stringify(geometry)}`);
      assert.ok(geometry.scroll > geometry.height, 'Fixture should exercise scrolling through results');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Page must not overflow horizontally');
      await page.locator('#bill-filter').fill('example');
      await page.selectOption('#snapshot-select', archive);
      await page.waitForFunction(v => selectedSnapshot === v, archive);
      assert.equal(await page.locator('#bill-filter').inputValue(), 'example');
      assert.match(await page.locator('#bill-updated').innerText(), /Apr 24, 2026/);
      const links = page.locator('#bills-table-body .bill-title-button');
      assert.equal(await links.count(), 80);
      await links.last().scrollIntoViewIfNeeded();
      assert.ok(await links.last().isVisible(), 'Last listing must be reachable');
      if (width <= 700 || height <= 500) assert.ok((await links.last().boundingBox()).height >= 44, 'Mobile listing needs a usable touch target');
      const popupPromise = page.waitForEvent('popup');
      await links.last().tap();
      const popup = await popupPromise; await popup.waitForLoadState();
      assert.match(popup.url(), /^https:\/\/www\.usajobs\.gov\/job\/\d+$/); await popup.close();
      await page.locator('#bill-filter').fill('no-matching-fixture-job');
      assert.match(await page.locator('#bills-table-body').innerText(), /No USAJOBS records matched/);
      await page.locator('#reset-filters').tap();
      assert.equal(await page.locator('#bill-filter').inputValue(), '');
      assert.equal(await page.locator('#snapshot-select').inputValue(), archive, 'Reset filters must retain the selected date');
      assert.deepEqual(errors, []);
      if (process.env.USAJOBS_SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.USAJOBS_SCREENSHOT_DIR, { recursive: true });
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: path.join(process.env.USAJOBS_SCREENSHOT_DIR, `${width}x${height}.png`) });
      }
    } finally { await context.close(); }
  });
}
