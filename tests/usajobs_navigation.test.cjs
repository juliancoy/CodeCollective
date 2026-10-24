const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../usa/jobs.js'), 'utf8');
const helper = source.match(/function getJobNavigationUrl\(bill\) \{[\s\S]*?\n\}/)[0];
const navigate = vm.runInNewContext(`(${helper})`);

test('cached records link to the official announcement instead of application status or arbitrary URLs', () => {
  assert.equal(navigate({ job_id: '866104100', detail_url: 'https://apply.usastaffing.gov/Application/ApplicationStatus', apply_url: 'javascript:alert(1)' }), 'https://www.usajobs.gov/job/866104100');
  assert.equal(navigate({ job_id: 'bad', apply_url: 'https://example.com' }), '');
  assert.equal(navigate({}), '');
});

const loader = source.match(/async function loadData\([^)]*\) \{[\s\S]*?\n\}/)[0];
const { gzipSync } = require('node:zlib');
test('R2 pages stay pinned to one version and retain the source retrieval date', async () => {
  const calls = [];
  const fetch = async (url) => {
    calls.push(String(url));
    if (url === '/api/jobs/meta') return Response.json({ version: 'v1', source_fetched_at: '2026-10-02T03:17:41Z', source_record_count: 2, states: { ALL: { shards: [{ page: 1, record_count: 1 }, { page: 2, record_count: 1 }] } } });
    const page = new URL(url, 'https://example.com').searchParams.get('page');
    const json = JSON.stringify({ version: 'v1', records: [{ job_id: page }] });
    return new Response(page === '1' ? gzipSync(json) : json);
  };
  const load = vm.runInNewContext(`(${loader})`, { fetch, Response, Blob, DecompressionStream, URLSearchParams, Uint8Array });
  const payload = await load();
  assert.equal(payload.records.length, 2);
  assert.equal(payload.fetched_at, '2026-10-02T03:17:41Z');
  assert.deepEqual(calls.slice(1), ['/api/jobs?version=v1&state=ALL&page=1', '/api/jobs?version=v1&state=ALL&page=2']);
});

test('failed R2 pages do not display a partial snapshot', async () => {
  const fetch = async (url) => url === '/api/jobs/meta'
    ? Response.json({ version: 'v1', source_record_count: 1, states: { ALL: { shards: [{ page: 1, record_count: 1 }] } } })
    : new Response('', { status: 503 });
  const load = vm.runInNewContext(`(${loader})`, { fetch, Response, Blob, DecompressionStream, URLSearchParams, Uint8Array });
  await assert.rejects(load(), /Jobs page unavailable: 503/);
});


test('choosing history requests metadata and pages from that exact version', async () => {
  const calls = [];
  const fetch = async (url) => {
    calls.push(String(url));
    if (url === '/api/jobs/meta?version=archived') return Response.json({ version: 'archived', source_fetched_at: '2026-04-24T17:31:43Z', source_record_count: 1, states: { ALL: { shards: [{ page: 1, record_count: 1 }] } } });
    return Response.json({ version: 'archived', records: [{ job_id: '123' }] });
  };
  const load = vm.runInNewContext(`(${loader})`, { fetch, Response, Blob, DecompressionStream, URLSearchParams, Uint8Array });
  const payload = await load('archived');
  assert.equal(payload.version, 'archived');
  assert.deepEqual(calls, ['/api/jobs/meta?version=archived', '/api/jobs?version=archived&state=ALL&page=1']);
});
