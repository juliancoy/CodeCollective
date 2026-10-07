import test from 'node:test'
import assert from 'node:assert/strict'
import worker from './worker.js'

test('portal update manifests stay fresh on every published mount', async () => {
  const env = { ASSETS: { fetch: async () => Response.json({ web: { buildNumber: 42 } }, { headers: { 'cache-control': 'public, max-age=300' } }) } }
  for (const path of ['/__portal_root/mobile-update.json']) {
    const response = await worker.fetch(new Request(`https://codecollective.us${path}`), env)
    assert.equal(response.status, 200)
    assert.equal(response.headers.get('cache-control'), 'no-store')
    assert.equal((await response.json()).web.buildNumber, 42)
  }
})
