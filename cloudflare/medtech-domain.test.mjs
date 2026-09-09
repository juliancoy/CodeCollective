import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';

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
