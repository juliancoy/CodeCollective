import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';

test('OrgPortal Timebank routes require a community choice and preserve link context', async () => {
  for (const path of ['/timebanking', '/timebanking/', '/p/timebanking', '/p/timebanking/']) {
    const response = await worker.fetch(new Request(`https://orgportal.cc${path}?listing=existing`), {});
    assert.equal(response.status, 308);
    assert.equal(response.headers.get('location'), 'https://orgportal.cc/communities?listing=existing&feature=timebank');
  }
});

test('OrgPortal install assets use the neutral bundle', async () => {
  const env = { ORGPORTAL_TENANT_HOSTS: 'orgportal.cc', ASSETS: { fetch: async request => new Response(new URL(request.url).pathname) } };
  for (const path of ['/orgportal.svg', '/orgportal.webmanifest', '/fonts/CLT-Mattone/web/Mattone-Black.woff2']) {
    const response = await worker.fetch(new Request('https://orgportal.cc' + path), env);
    assert.equal(await response.text(), '/__portal_root' + path);
  }
  const favicon = await worker.fetch(new Request('https://orgportal.cc/favicon.ico'), env);
  assert.equal(favicon.headers.get('location'), 'https://orgportal.cc/orgportal.svg');
});
