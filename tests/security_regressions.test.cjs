const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

const orgBackend = readFileSync('portal_src/org-backend/org.py', 'utf8');
const eventsList = readFileSync('eventslist.html', 'utf8');

test('public account creation cannot seed balances from client data', () => {
  assert.match(orgBackend, /balance=Decimal\('0\.00'\)/);
  assert.doesNotMatch(orgBackend, /balance=account_data\.initial_deposit/);
  assert.doesNotMatch(orgBackend, /description="Initial account deposit"/);
});

test('public transaction endpoint blocks minting and requires atomic debits', () => {
  assert.match(orgBackend, /privileged_types\s*=\s*\{TransactionType\.UBI_PAYMENT,\s*TransactionType\.GRANT\}/);
  assert.match(orgBackend, /if transaction_data\.transaction_type in privileged_types:\s*\n\s*raise HTTPException\(status_code=403/);
  assert.match(orgBackend, /debit_result\s*=\s*await conn\.execute/);
  assert.match(orgBackend, /if debit_result != "UPDATE 1":\s*\n\s*raise HTTPException\(status_code=400,\s*detail="Insufficient funds"\)/);
  assert.match(orgBackend, /except HTTPException:\s*\n\s*session\.rollback\(\)\s*\n\s*raise\s*\n\s*except Exception as e:/);
});

test('ledger-wide endpoints require admin authorization', () => {
  assert.match(orgBackend, /def require_admin_user\(current_user: dict\) -> None:/);
  assert.match(orgBackend, /async def list_accounts\([\s\S]*?require_admin_user\(current_user\)/);
  assert.match(orgBackend, /async def get_recent_transactions\([\s\S]*?require_admin_user\(current_user\)/);
});

test('events list escapes scraped event fields before html template insertion', () => {
  assert.match(eventsList, /function escapeHtml\(value\)/);
  assert.match(eventsList, /function safeUrl\(url\)/);
  assert.match(eventsList, /const imageUrl = safeUrl\(event\.imageUrl\)/);
  assert.match(eventsList, /const eventUrl = safeUrl\(event\.url\)/);
  assert.match(eventsList, /const eventName = escapeHtml\(event\.name \|\| 'Untitled'\)/);
  assert.match(eventsList, /<h3 class="event-title">\$\{eventName\}<\/h3>/);
  assert.match(eventsList, /<div class="event-time">\$\{escapeHtml\(timeRange\)\}<\/div>/);
  assert.match(eventsList, /\$\{escapeHtml\(locationText\)\}/);
  assert.match(eventsList, /\$\{escapeHtml\(shortDescription\)\}/);
  assert.doesNotMatch(eventsList, /<h3 class="event-title">\$\{event\.name\}<\/h3>/);
  assert.doesNotMatch(eventsList, /href="\$\{event\.url\}"/);
  assert.doesNotMatch(eventsList, /src="\$\{event\.imageUrl\}"/);
});
