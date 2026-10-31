import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';

for (const agent of ['Mozilla/5.0', 'Googlebot/2.1']) {
  test(`canonical origin redirects preserve URL for ${agent}`, async () => {
    for (const base of ['http://codecollective.us', 'http://www.codecollective.us', 'https://www.codecollective.us']) {
      const r = await worker.fetch(new Request(base + '/calendar?city=dc', {headers:{'user-agent':agent}}), {});
      assert.equal(r.status, 308);
      assert.equal(r.headers.get('location'), 'https://codecollective.us/calendar?city=dc');
    }
  });
}

test('missing public pages and event routes preserve real 404 responses', async () => {
  const env = {ASSETS:{fetch:async () => new Response('Page not found', {status:404})}};
  for (const path of ['/missing', '/events/deleted-event', '/events/deleted-event.html']) {
    const r = await worker.fetch(new Request('https://codecollective.us'+path), env);
    assert.equal(r.status,404);
    assert.equal(await r.text(),'Page not found');
  }
});
