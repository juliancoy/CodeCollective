import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './worker.js';

test('history lists saved snapshots across R2 listing pages, preserving retrieval dates', async () => {
  const old = 'v20260424T173211Z', latest = 'v20260501T120000Z';
  const requests = [];
  const rows = {
    'jobs/latest.json': { version: latest },
    [`jobs/${old}/manifest.json`]: { version: old, source_fetched_at: '2026-04-24T17:31:43Z', source_record_count: 11806 },
    [`jobs/${latest}/manifest.json`]: { version: latest, source_fetched_at: '2026-05-01T12:00:00Z', source_record_count: 12000 },
  };
  const env = { JOBS_BUCKET: {
    async get(key) { return rows[key] ? { json: async () => rows[key] } : null; },
    async list(options) {
      requests.push(options);
      return options.cursor
        ? { delimitedPrefixes: [`jobs/${latest}/`, 'jobs/not-a-version/'], truncated: false }
        : { delimitedPrefixes: [`jobs/${old}/`], truncated: true, cursor: 'next' };
    },
  } };
  const response = await worker.fetch(new Request('https://codecollective.us/api/jobs/versions'), env, {});
  assert.equal(response.status, 200);
  const history = await response.json();
  assert.equal(history.latest, latest);
  assert.deepEqual(history.versions.map(row => row.version), [latest, old]);
  assert.equal(history.versions[1].source_fetched_at, '2026-04-24T17:31:43Z');
  assert.equal(requests[1].cursor, 'next');
  assert.equal(requests[0].delimiter, '/');
});
