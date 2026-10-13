import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';
test('portal tenants use the independent Worker with the original request intact', async () => {
  for (const host of ['orgportal.cc', 'timebank.codecollective.us', 'medtech.social']) {
    for (const path of ['/events/example', '/assets/app.js', '/pidp/auth/me', '/api/chat/socket']) {
      const request = new Request(`https://${host}${path}`, { headers: { authorization: 'Bearer fixture', cookie: 'session=fixture', upgrade: 'websocket' } });
      const expected = { status: 101, webSocket: {} };
      const result = await worker.fetch(request, {
        ORGPORTAL_SITE_HOSTS: 'orgportal.cc,medtech.social',
        ORGPORTAL_WEB: { fetch: async forwarded => { assert.equal(forwarded, request); return expected; } },
        ASSETS: { fetch() { throw Error('Portal assets must not use the static site'); } },
      });
      assert.equal(result, expected);
    }
  }
});
