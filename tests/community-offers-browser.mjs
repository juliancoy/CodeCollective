// Real website Worker, static assets and portal UI; real org Worker + SQLite.
// Only identity and storage use the existing timebank acceptance fixture.
// Setup: build portal/web with VITE_PUBLIC_BASE=/p/ into PORTAL_BUILD_DIR,
// then run a Selenium Chrome container on port 4446 and execute this file.
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'portal/web/package.json'));
const { chromium, expect } = require('@playwright/test');
const portalBuild = process.env.PORTAL_BUILD_DIR || '/tmp/codecollective-offers-portal';
const out = process.env.OFFERS_SHOTS || '/tmp/codecollective-offers-acceptance';
const grid = process.env.SELENIUM_REMOTE_URL || 'http://127.0.0.1:4446';
const site = (await import(pathToFileURL(path.join(root, 'cloudflare/worker.js')).href)).default;
await mkdir(out, { recursive: true });
await readFile(path.join(portalBuild, 'index.html'));
const fixture = spawn(process.execPath, ['--import', 'tsx', 'test/helpers/timebankServer.ts'], {
  cwd: path.join(root, 'portal/org-worker'), env: { ...process.env, TIMEBANK_TEST_PORT: '0' },
  stdio: ['ignore', 'pipe', 'inherit'],
});
let browser, sessionId;
try {
  const upstream = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Fixture did not start')), 15000);
    fixture.once('exit', code => { clearTimeout(timer); reject(new Error(`Fixture exited: ${code}`)); });
    fixture.stdout.on('data', data => {
      const match = String(data).match(/http:\/\/127\.0\.0\.1:\d+/);
      if (match) { clearTimeout(timer); resolve(match[0]); }
    });
  });
  const api = async (pathname, { user = 'alice', community = 'codecollective.us', ...options } = {}) => {
    const response = await fetch(`${upstream}/api/timebank${pathname}`, {
      ...options, headers: { Authorization: `Bearer ${user}`, 'x-forwarded-host': community, 'Content-Type': 'application/json', ...options.headers },
    });
    assert.ok(response.ok, `${pathname}: ${response.status} ${await response.clone().text()}`);
    return response;
  };
  const post = async (title, options = {}) => {
    const { community, user, visibility = 'public', kind = 'offer' } = options;
    const response = await api('/listings', { user, community, method: 'POST', body: JSON.stringify({
      id: crypto.randomUUID(), kind, title, description: 'Friendly help from your neighbors.', minutes: 90,
      location: 'Baltimore', category: 'Tech help', visibility,
    }) });
    return response.json();
  };
  const session = await fetch(`${grid}/session`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capabilities: { alwaysMatch: { browserName: 'chrome', 'goog:chromeOptions': { args: ['--headless=new', '--no-sandbox'] } } } }),
  }).then(response => response.json());
  sessionId = session.value.sessionId;
  const cdp = new URL(session.value.capabilities['se:cdp']);
  cdp.host = new URL(grid).host;
  browser = await chromium.connectOverCDP(cdp.toString());
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.mp4': 'video/mp4' };
  const env = {
    ORG_API_ORIGIN: upstream, PIDP_PROXY_ORIGIN: upstream,
    ASSETS: { fetch: async request => {
      const pathname = new URL(request.url).pathname;
      const isPortal = pathname.startsWith('/p/');
      const filename = path.join(isPortal ? portalBuild : root, (isPortal ? pathname.slice(3) : pathname.slice(1)) || 'index.html');
      try { return new Response(await readFile(filename), { headers: { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream' } }); }
      catch { return new Response('Not found', { status: 404 }); }
    } },
  };
  let failOffers = false;
  const errors = [];
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (!url.hostname.endsWith('codecollective.us')) return route.abort();
    if (url.pathname.includes('/timebank/public-offers')) {
      assert.equal(request.headers().authorization, undefined);
      assert.equal(request.headers().cookie, undefined);
      if (failOffers) return route.fulfill({ status: 503, body: 'Unavailable' });
    }
    // Identity calls remain inside the local fixture too.
    const response = url.hostname === 'id.codecollective.us'
      ? await fetch(`${upstream}${url.pathname}${url.search}`)
      : await site.fetch(new Request(request.url(), { method: request.method(), headers: request.headers() }), env);
    await route.fulfill({ status: response.status, headers: Object.fromEntries(response.headers), body: Buffer.from(await response.arrayBuffer()) });
  });
  await page.goto('https://codecollective.us/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#community-offers-status')).toContainText('No public offers yet.');
  await expect(page.locator('#community-offers-more')).toBeHidden();

  for (let i = 0; i < 13; i++) await post(`Neighbor skill ${i + 1}`);
  const alice = await post('Laptop setup with Alice');
  const bob = await post('Bicycle repair with Bob', { community: 'bmoretimebank.codecollective.us', user: 'bob' });
  await api(`/listings/${bob.id}/image`, { user: 'bob', community: 'bmoretimebank.codecollective.us', method: 'PUT', headers: { 'Content-Type': 'image/png' }, body: await readFile(path.join(root, 'images/unity5_photo.png')) });
  await post('Members only offer', { visibility: 'members' });
  await post('Request for help', { kind: 'request' });
  const closed = await post('Closed offer');
  await api(`/listings/${closed.id}`, { method: 'PATCH', body: JSON.stringify({ status: 'closed' }) });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('.community-offer')).toHaveCount(12);
  await expect(page.locator('#community-offers')).not.toContainText('Members only offer');
  await expect(page.locator('#community-offers')).not.toContainText('Request for help');
  await expect(page.locator('#community-offers')).not.toContainText('Closed offer');
  await expect(page.locator('#community-offers')).toContainText('Bmore Timebank');
  await expect(page.locator('#community-offers')).toContainText('Code Collective Timebank');
  const bobCard = page.locator(`[data-offer-id="${bob.id}"]`);
  await expect(bobCard).toContainText('Bob · Baltimore');
  await expect(bobCard).toContainText('1.5 hours');
  await bobCard.scrollIntoViewIfNeeded();
  await expect.poll(() => bobCard.locator('img').evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
  const contrast = await page.locator('#community-offers .community-offers-action').first().evaluate(button => {
    const luminance = color => color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => {
      const channel = value / 255;
      return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
    }).reduce((total, channel, index) => total + channel * [.2126, .7152, .0722][index], 0);
    const style = getComputedStyle(button), text = luminance(style.color), background = luminance(style.backgroundColor);
    return (Math.max(text, background) + .05) / (Math.min(text, background) + .05);
  });
  assert.ok(contrast >= 4.5, `Offer action contrast: ${contrast}`);
  assert.equal(await page.locator('#community-offers-list > li').first().evaluate(li => getComputedStyle(li).listStyleType), 'none');
  await page.locator('#community-offers').screenshot({ path: path.join(out, 'desktop-offers.png'), style: '.main-nav { visibility: hidden; }' });
  await page.getByRole('button', { name: 'Show more offers' }).click();
  await expect(page.locator('.community-offer')).toHaveCount(15);
  await expect(page.locator('#community-offers-more')).toBeHidden();
  assert.equal(new Set(await page.locator('.community-offer').evaluateAll(cards => cards.map(card => card.dataset.offerId))).size, 15);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#community-offers').scrollIntoViewIfNeeded();
  assert.equal(await page.locator('#community-offers').evaluate(section => section.scrollWidth <= section.clientWidth), true);
  await bobCard.screenshot({ path: path.join(out, 'mobile-offer.png') });
  await bobCard.getByRole('link', { name: 'View offer: Bicycle repair with Bob' }).click();
  await expect(page).toHaveURL(`https://bmoretimebank.codecollective.us/p/timebanking?listing=${bob.id}`);
  await expect(page.locator('dialog[open]')).toContainText('Bicycle repair with Bob');
  await expect(page.locator('dialog[open]')).toContainText('Shared by Bob');
  await page.screenshot({ path: path.join(out, 'portal-offer.png') });

  await api(`/listings/${bob.id}`, { user: 'bob', community: 'bmoretimebank.codecollective.us', method: 'PATCH', body: JSON.stringify({ visibility: 'members' }) });
  await api(`/listings/${alice.id}`, { method: 'PATCH', body: JSON.stringify({ status: 'closed' }) });
  await page.goto('https://codecollective.us/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#community-offers-status')).toContainText('12 public offers shown.');
  await expect(page.locator(`[data-offer-id="${bob.id}"]`)).toHaveCount(0);
  await expect(page.locator(`[data-offer-id="${alice.id}"]`)).toHaveCount(0);
  failOffers = true;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#community-offers-status')).toContainText('could not be loaded');
  failOffers = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.locator('.community-offer')).toHaveCount(12);
  const unsafeTitle = '<img src=x onerror=alert(1)>';
  await post(unsafeTitle);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#community-offers')).toContainText(unsafeTitle);
  await expect(page.locator('#community-offers h3 img')).toHaveCount(0);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ result: 'passed', checks: ['real Worker and shared database', 'public offers across communities', 'original portal detail navigation', 'public photo', 'pagination', 'desktop and mobile', 'visibility and closure updates', 'empty and retry states', 'member text rendered safely'], screenshots: out }, null, 2));
} finally {
  if (browser) await browser.close();
  if (sessionId) await fetch(`${grid}/session/${sessionId}`, { method: 'DELETE' });
  fixture.kill('SIGTERM');
}
