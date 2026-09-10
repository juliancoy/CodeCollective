import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';

test('site health reports deployment metadata without caching', async () => {
  const response = await worker.fetch(new Request('https://bmoretimebank.codecollective.us/health'), {
    CF_VERSION_METADATA: { id: 'worker-version-fixture' },
    ASSETS: {
      fetch: async () => Response.json({ commit: 'a'.repeat(40), dirty: false, builtAt: '2026-09-09T00:00:00.000Z' }),
    },
  });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  const payload = await response.json();
  assert.equal(payload.ok, true);
  assert.equal(payload.service, 'codecollective-site');
  assert.equal(payload.commit, 'a'.repeat(40));
  assert.equal(payload.dirty, false);
  assert.equal(payload.builtAt, '2026-09-09T00:00:00.000Z');
  assert.equal(payload.workerVersionId, 'worker-version-fixture');
  assert.equal(payload.hostname, 'bmoretimebank.codecollective.us');
  assert.equal(payload.environment, 'production');
  assert.match(payload.time, /^\d{4}-\d{2}-\d{2}T/);
});

test('the cache link clears only the current origin cache and returns to the requested login', async () => {
  const query = '?portalProfile=baltimore-medtech&next=%2Fcommunity';
  const response = await worker.fetch(new Request(`https://community.medtech.social/p/clear-cache${query}`), {});
  assert.equal(response.status, 303);
  assert.equal(response.headers.get('location'), `https://community.medtech.social/p/users/login${query}`);
  assert.equal(response.headers.get('clear-site-data'), '"cache"');
  assert.equal(response.headers.get('cache-control'), 'no-store');
});

test('MedTech root opens the portal on its own hostname', async () => {
  const response = await worker.fetch(new Request('https://community.medtech.social/'), {});
  assert.equal(response.headers.get('location'), 'https://community.medtech.social/p/');
});

test('MedTech auth uses host-only secure cookies and preserves all cookie headers', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://pidp.example/auth/session/login');
    assert.equal(options.headers.get('x-forwarded-host'), 'community.medtech.social');
    const headers = new Headers();
    headers.append('set-cookie', 'pidp_session=fixture; Domain=codecollective.us; Path=/; HttpOnly; Secure; SameSite=Lax');
    headers.append('set-cookie', 'pidp_oauth_state=; Max-Age=0; Path=/');
    return new Response('{}', { headers });
  });
  const response = await worker.fetch(new Request('https://community.medtech.social/pidp/auth/session/login', { method: 'POST', body: 'fixture' }), { PIDP_PROXY_ORIGIN: 'https://pidp.example' });
  const cookies = response.headers.getSetCookie();
  assert.equal(cookies.length, 2);
  assert.ok(cookies.every(cookie => !/domain=/i.test(cookie)));
  assert.match(cookies[0], /HttpOnly; Secure; SameSite=Lax/);
  assert.equal(response.headers.get('cache-control'), 'no-store');
});

test('MedTech MCP protected-resource discovery proxies to the org worker without stripping the path', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://org.example/.well-known/oauth-protected-resource/api/org/mcp');
    assert.equal(options.headers.get('x-forwarded-host'), 'community.medtech.social');
    return Response.json({ resource: 'https://community.medtech.social/api/org/mcp' }, { headers: { 'cache-control': 'no-store' } });
  });
  const response = await worker.fetch(new Request('https://community.medtech.social/.well-known/oauth-protected-resource/api/org/mcp'), { ORG_API_ORIGIN: 'https://org.example' });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal((await response.json()).resource, 'https://community.medtech.social/api/org/mcp');
});
