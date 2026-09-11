import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';

const origin = 'https://timebank.codecollective.us';
const env = {
  ORG_API_ORIGIN: 'https://org.example',
  ASSETS: { fetch: async request => new Response(new URL(request.url).pathname) },
};

function community(t, status = 200) {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://org.example/api/portal/tenant');
    assert.equal(options.headers['x-forwarded-host'], 'timebank.codecollective.us');
    return Response.json({ id: 'timebank' }, { status });
  });
}

test('tenant root and nested routes serve the shared portal without redirecting', async t => {
  community(t);
  for (const path of ['/', '/users/login', '/chat', '/auth/callback', '/users/some.member']) {
    const response = await worker.fetch(new Request(origin + path, { headers: { accept: 'text/html' } }), env);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('location'), null);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.equal(await response.text(), '/__portal_root/index.html');
  }
});

test('HEAD navigation to a dotted profile requests the portal entrypoint without a body', async t => {
  community(t);
  const response = await worker.fetch(new Request(origin + '/users/some.member', {
    method: 'HEAD', headers: { accept: 'text/html' },
  }), {
    ...env,
    ASSETS: { fetch: async request => {
      assert.equal(new URL(request.url).pathname, '/__portal_root/index.html');
      assert.equal(request.method, 'HEAD');
      return new Response(null, { headers: { 'content-type': 'text/html' } });
    } },
  });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('content-type'), 'text/html');
  assert.equal(await response.text(), '');
});

test('tenant favicon redirects to the portal icon while the main site keeps its icon', async () => {
  const response = await worker.fetch(new Request(origin + '/favicon.ico'), env);
  assert.equal(response.status, 308);
  const icon = await worker.fetch(new Request(response.headers.get('location')), env);
  assert.equal(await icon.text(), '/__portal_root/codecollective_logo.png');
  const mainIcon = await worker.fetch(new Request('https://codecollective.us/favicon.ico'), env);
  assert.equal(mainIcon.headers.get('location'), 'https://codecollective.us/images/favicons/favicon.png');
});

test('redundant tenant URLs redirect to the canonical route with query strings intact', async t => {
  community(t);
  for (const [path, destination] of [
    ['/p/timebanking?listing=abc&tab=home', '/?listing=abc&tab=home'],
    ['/timebanking?listing=abc', '/?listing=abc'],
    ['/p/', '/'], ['/p', '/'], ['/p/index.html', '/'],
    ['/p/users/login?next=%2F', '/users/login?next=%2F'],
  ]) {
    const response = await worker.fetch(new Request(origin + path), env);
    assert.equal(response.status, 308);
    assert.equal(response.headers.get('location'), origin + destination);
  }
});

test('tenant assets use the shared bundle and missing assets remain 404', async () => {
  const legacyAsset = await worker.fetch(new Request(origin + '/p/assets/index.js'), env);
  assert.equal(legacyAsset.status, 308);
  assert.equal(legacyAsset.headers.get('location'), `${origin}/assets/index.js`);
  for (const path of ['/assets/index.js', '/push-sw.js', '/images/google-g-logo.svg']) {
    const response = await worker.fetch(new Request(origin + path), env);
    assert.equal(await response.text(), `/__portal_root${path}`);
    assert.equal(response.headers.get('location'), null);
  }
  const response = await worker.fetch(new Request(origin + '/missing.js'), {
    ASSETS: { fetch: async () => new Response('Not found', { status: 404 }) },
  });
  assert.equal(response.status, 404);
});

test('unconfigured and unavailable tenants do not serve a different community', async t => {
  for (const status of [404, 500]) {
    community(t, status);
    const response = await worker.fetch(new Request(origin + '/'), env);
    assert.equal(response.status, status === 404 ? 404 : 503);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    t.mock.restoreAll();
  }
});

test('tenant API requests retain the hostname and bypass page routing', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://org.example/api/timebank');
    assert.equal(options.headers.get('x-forwarded-host'), 'timebank.codecollective.us');
    return Response.json({ community: { id: 'timebank' } });
  });
  const response = await worker.fetch(new Request(origin + '/api/org/api/timebank', {
    headers: { 'x-forwarded-host': 'bmoretimebank.codecollective.us' },
  }), env);
  assert.equal((await response.json()).community.id, 'timebank');
});

test('tenant pidp proxy emits host-only session cookies for custom domains', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://pidp.example/auth/session/login');
    assert.equal(options.headers.get('x-forwarded-host'), 'medtech.social');
    return new Response('{}', {
      headers: {
        'content-type': 'application/json',
        'set-cookie': 'pidp_session=abc; Path=/; Max-Age=3600; Domain=codecollective.us; HttpOnly; Secure; SameSite=Lax',
      },
    });
  });
  const response = await worker.fetch(new Request('https://medtech.social/pidp/auth/session/login', { method: 'POST' }), {
    ...env,
    PIDP_PROXY_ORIGIN: 'https://pidp.example',
    ORGPORTAL_TENANT_HOSTS: 'medtech.social',
  });
  const cookie = response.headers.get('set-cookie');
  assert.match(cookie, /^pidp_session=abc;/);
  assert.doesNotMatch(cookie, /Domain=/i);
});

test('main pidp proxy keeps configured parent-domain session cookies', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://pidp.example/auth/session/login');
    assert.equal(options.headers.get('x-forwarded-host'), 'codecollective.us');
    return new Response('{}', {
      headers: {
        'content-type': 'application/json',
        'set-cookie': 'pidp_session=abc; Path=/; Max-Age=3600; Domain=codecollective.us; HttpOnly; Secure; SameSite=Lax',
      },
    });
  });
  const response = await worker.fetch(new Request('https://codecollective.us/pidp/auth/session/login', { method: 'POST' }), {
    ...env,
    PIDP_PROXY_ORIGIN: 'https://pidp.example',
  });
  const cookie = response.headers.get('set-cookie');
  assert.match(cookie, /Domain=codecollective\.us/i);
});

test('configured custom domains mount the same tenant portal root', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://org.example/api/portal/tenant');
    assert.equal(options.headers['x-forwarded-host'], 'medtech.social');
    return Response.json({ id: 'baltimore-medtech' });
  });
  const response = await worker.fetch(new Request('https://medtech.social/community', {
    headers: { accept: 'text/html' },
  }), { ...env, ORGPORTAL_TENANT_HOSTS: 'medtech.social' });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), '/__portal_root/index.html');
});
