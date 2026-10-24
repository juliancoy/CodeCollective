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
