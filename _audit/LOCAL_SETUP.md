# Local portal stack — runbook

Stands up the production code path (Cloudflare Workers) locally via `wrangler dev` with
local D1 (miniflare/SQLite). No Docker, no Cloudflare login, no OAuth secrets needed —
which is exactly what makes the **email/password** (non-social) sign-in path testable.

## Components

| Service     | Dir                         | Local URL               | Notes |
|-------------|-----------------------------|-------------------------|-------|
| PIdP        | `portal/pidp/serverless`    | http://127.0.0.1:8787   | identity provider (auth core) |
| org-worker  | `portal/org-worker`         | http://127.0.0.1:8788   | org/governance/UBI/finance API; points at local PIdP |

Social login is **disabled** locally (no `GOOGLE_CLIENT_ID`/`GITHUB_CLIENT_ID`), so
`/app/login` renders the password form instead of auto-redirecting to OAuth.

## Bring it up

```sh
# --- PIdP ---
cd portal/pidp/serverless
npm install
printf 'SECRET_KEY=%s\nENV=dev\n' "$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")" > .dev.vars
npm run db:migrate:local                       # apply D1 migrations
npx wrangler dev --port 8787 --ip 127.0.0.1 &  # leave running

# --- org-worker (separate terminal) ---
cd portal/org-worker
npm install
printf 'PIDP_BASE_URL=http://127.0.0.1:8787\nADMIN_EMAILS=admin@example.com\n' > .dev.vars
npx wrangler d1 migrations apply org --local
npx wrangler dev --port 8788 --ip 127.0.0.1 &
```

`.dev.vars` holds local secrets and is gitignored (do not commit).

## Smoke check (email/password, end to end)

```sh
PID=http://127.0.0.1:8787; ORG=http://127.0.0.1:8788

# owner: register -> login -> me
curl -s -X POST $PID/auth/register -H 'content-type: application/json' \
  -d '{"email":"alice@example.com","password":"Sup3r-Secret!"}'
TOK=$(curl -s -X POST $PID/auth/session/login \
  --data-urlencode username=alice@example.com --data-urlencode password='Sup3r-Secret!' | jq -r .access_token)
curl -s $PID/auth/me -H "authorization: Bearer $TOK"

# the same token type authenticates the org API (cross-worker auth)
curl -s $ORG/api/network/contact/me -H "authorization: Bearer $TOK"
```

To make a portal **member** (website_user) instead of an owner: have an owner create a
website (`POST /websites {name,slug}`), then `POST /websites/:slug/auth/register` and
`POST /websites/:slug/auth/token` (this endpoint takes **JSON** `{email,password}`, unlike
the owner endpoints which take **form** `username/password`).

## Tests

```sh
cd portal/pidp/serverless
npm test                                   # full suite (incl. the sign-in tests)
node --test test/auth-password.test.mjs    # just the non-social sign-in tests
```

`test/auth-password.test.mjs` reuses a running server if one is up, otherwise it boots its
own `wrangler dev` (and applies migrations) and tears it down. Override the target with
`PIDP_BASE_URL=...`.

## Endpoint quirks worth knowing
- `POST /auth/register` → JSON `{email,password,full_name?}` (returns the user, no token).
- `POST /auth/session/login` and `POST /auth/token` → **form** `username` + `password`.
- `POST /websites/:slug/auth/token` → **JSON** `{email,password}`.
- Auth to the org API is a Bearer token; org-worker validates it by calling PIdP `/auth/me`.
