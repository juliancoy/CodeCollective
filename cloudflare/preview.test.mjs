import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker from './worker.js';
import { deploymentResponse, deploymentCookie, deploymentCachePolicy, isDeploymentAssetRequest } from '../../OrgPortal/web/deployment.mjs';
const base = 'https://lifetech.fyi';
const development = { cookie: `${deploymentCookie}=development` };

test('development Worker has no public entrypoints or production resources', () => {
  const config = readFileSync(new URL('../wrangler.preview.toml', import.meta.url), 'utf8');
  assert.match(config, /workers_dev = false/);
  assert.match(config, /preview_urls = false/);
  assert.doesNotMatch(config, /^\s*(routes|\[\[r2_buckets\]\]|\[\[d1_databases\]\]|\[\[services\]\]|ORG_API_ORIGIN|PIDP_API_ORIGIN)/m);
});
test('private asset service rejects API, writes and requests with no mount', async () => {
  const env = { WEB_PREVIEW: 'true', ASSETS: { fetch() { throw Error('Must not read assets'); } } };
  for (const path of ['/api/org/api/organizations', '/pidp/auth/login', '/auth/callback']) assert.equal((await worker.fetch(new Request(base + path, { headers: { 'x-preview-mount': 'lifetech' } }), env)).status, 404);
  assert.equal((await worker.fetch(new Request(base + '/', { method: 'POST' }), env)).status, 404);
  assert.equal((await worker.fetch(new Request(base + '/'), env)).status, 403);
});
test('preference is host-bound, requires same origin, rejects bad modes and clears production selection', async () => {
  const env = { DEV_ASSETS: {} };
  const get = await deploymentResponse(new Request(base + '/__portal/deployment', { headers: development }), env);
  assert.deepEqual(await get.json(), { mode: 'development', available: true });
  for (const [origin, mode, expected] of [['https://attacker.test', 'development', 403], [base, 'bad', 400], [base, 'development', 200], [base, 'production', 200]]) {
    const response = await deploymentResponse(new Request(base + '/__portal/deployment', { method: 'POST', headers: { origin, 'content-type': 'application/json' }, body: JSON.stringify({ mode }) }), env);
    assert.equal(response.status, expected);
    if (expected === 200) {
      const cookie = response.headers.get('set-cookie');
      assert.match(cookie, /HttpOnly; Secure; SameSite=Lax/);
      assert.doesNotMatch(cookie, /Domain=/);
      assert.match(cookie, mode === 'production' ? /Max-Age=0;/ : /Max-Age=7776000;/);
    }
  }
  const unavailable = await deploymentResponse(new Request(base + '/__portal/deployment', { method: 'POST', headers: { origin: base }, body: JSON.stringify({ mode: 'development' }) }), {});
  assert.equal(unavailable.status, 503);
});
test('preview keeps exact URL, strips credentials, varies caches and never diverts API or auth requests', async () => {
  let seen;
  const env = { DEV_ASSETS: { fetch: async request => { seen = request; return new Response('preview', { headers: { 'content-type': 'text/plain', 'set-cookie': 'untrusted=1' } }); } } };
  const request = new Request(base + '/profile?view=public', { headers: { ...development, authorization: 'Bearer fixture-token' } });
  const response = await deploymentResponse(request, env);
  assert.equal(seen.url, request.url);
  assert.equal(seen.headers.has('cookie'), false);
  assert.equal(seen.headers.has('authorization'), false);
  assert.equal(response.headers.has('set-cookie'), false);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  assert.equal(response.headers.get('vary'), 'Cookie');
  assert.equal(response.headers.get('x-portal-deployment'), 'development');
  for (const path of ['/api/org/api/organizations', '/pidp/auth/login', '/auth/callback', '/.well-known/oauth-protected-resource/api/org/mcp', '/push-sw.js', '/robots.txt', '/sitemap.xml']) assert.equal(await deploymentResponse(new Request(base + path, { headers: development }), env), null);
  assert.equal(await deploymentResponse(new Request(base + '/', { method: 'POST', headers: development }), env), null);
  assert.equal(await deploymentResponse(new Request(base + '/'), env), null);
  const deployed = deploymentCachePolicy(new Response('deployed', { headers: { 'content-type': 'text/html' } }), env);
  assert.equal(deployed.headers.get('vary'), 'Cookie');
  assert.equal(deployed.headers.get('cache-control'), 'private, no-store');
});
test('private assets resolve both portal mounts and preserve missing asset 404s', async () => {
  const env = { WEB_PREVIEW: 'true', ASSETS: { fetch: async request => {
    const path = new URL(request.url).pathname;
    if (['/p/index.html', '/__portal_root/index.html', '/__portal_root/assets/root.js', '/ecosystem/index.html', '/about.html'].includes(path)) return Response.json({ path });
    return new Response('missing', { status: 404 });
  } } };
  for (const [mount, path, expected] of [['portal', '/p/profile', '/p/index.html'], ['root', '/profile', '/__portal_root/index.html'], ['lifetech', '/profile', '/__portal_root/index.html'], ['lifetech', '/about', '/about.html'], ['lifetech', '/ecosystem', '/ecosystem/index.html'], ['lifetech', '/assets/root.js', '/__portal_root/assets/root.js']]) {
    const response = await worker.fetch(new Request(base + path, { headers: { 'x-preview-mount': mount } }), env);
    assert.equal((await response.json()).path, expected);
  }
  assert.equal((await worker.fetch(new Request(base + '/assets/missing.js', { headers: { 'x-preview-mount': 'lifetech' } }), env)).status, 404);
});

test('deployment caching leaves WebSocket upgrades and identity image requests untouched', () => {
  const upgrade = { status: 101 };
  assert.equal(deploymentCachePolicy(upgrade, { DEV_ASSETS: {} }), upgrade);
  assert.equal(isDeploymentAssetRequest(new Request(base + '/socket', { headers: { upgrade: 'websocket' } })), false);
  assert.equal(isDeploymentAssetRequest(new Request(base + '/pidp/avatars/user.png')), false);
});

test('avatar caching survives development selection without varying on session cookies', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response('fixture image', { headers: { 'content-type': 'image/png', 'cache-control': 'public, max-age=31536000, immutable', etag: '"fixture-avatar"' } });
  try {
    const response = await worker.fetch(new Request('https://codecollective.us/pidp/avatars/fixture.png', { headers: development }), {
      DEV_ASSETS: { fetch() { throw Error('Avatar requests must stay in PIdP'); } },
      PIDP_PROXY_ORIGIN: 'https://pidp-fixture.example.test',
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'public, max-age=31536000, immutable');
    assert.equal(response.headers.get('etag'), '"fixture-avatar"');
    assert.equal(response.headers.get('vary'), null);
    assert.equal(response.headers.get('x-portal-deployment'), null);
  } finally { globalThis.fetch = originalFetch; }
});
