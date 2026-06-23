# Code Collective — Org Portal Audit

**Target:** https://codecollective.us/p/ (React/Vite SPA) · `id.codecollective.us` (PIdP identity) · `org-codecollective.jcloiacon.workers.dev` (org API)
**Method:** Grey-box — live black-box probing via Selenium Grid (172.24.254.44:4444) + curl, plus source review of `portal/web`, `portal/org-worker`, `portal/pidp/serverless`.
**Date:** 2026-06-11
**Scope limit:** The full app sits behind PIdP OAuth (Google/GitHub). Without portal credentials, live testing covered the unauthenticated surface + API authorization; the authenticated UI/API was reviewed from source only.

---

## Severity summary

| # | Severity | Finding |
|---|----------|---------|
| 1 | High | Test auth backdoor `/auth/smoke-token` is **enabled in production** (mints owner token for any email given a shared secret) |
| 2 | Medium | Open redirect in PIdP login `next` handling (protocol-relative `//evil.com` bypass) |
| 3 | Medium | No HTTP security headers on any origin (HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy) |
| 4 | Medium (latent) | Admin granted from self-storable `identity_data` — no separation of privilege claims from user profile data |
| 5 | Low | Public endpoints expose internal user UUIDs; governance motions world-readable & unthrottled |
| 6 | Low | Non-constant-time secret comparisons (ingest token, smoke secret, password hash) |
| 7 | Info | Wildcard CORS on token API; inconsistent CORS between endpoints |
| 8 | Info | Login-page accessibility: serious color-contrast on a link, missing `h1`, no meta description |

---

## Findings

### 1. [HIGH] Production test backdoor: `POST /auth/smoke-token`
`portal/pidp/serverless/src/index.ts:530`. The endpoint returns **403 "Smoke token secret is invalid"** in production (an empty secret returns 404), which proves `SMOKE_TEST_SECRET` is configured live. Given the secret, it mints a valid **owner** session token/cookie for *any* active email — i.e. full impersonation of any account, including owners/admins. Protection is one shared secret, compared non-constant-time, with no rate limiting. `chat.md` calls it "not an impersonation path," but functionally it is one (conditioned on the secret).
- **Risk:** Secret leak (CI logs, env files, docs) or brute force (no throttle, unknown entropy) → account takeover at the identity layer.
- **Fix:** Unset `SMOKE_TEST_SECRET` in the production PIdP Worker. Defense-in-depth: gate the route behind `ENV !== "production"` in code; add rate limiting; restrict to a non-prod hostname.

### 2. [MEDIUM] Open redirect in login `next` parameter
`redirectTarget` (`index.ts:122`) and `resolveRedirectTarget` (`oauth.ts:169`) accept any target where `target.startsWith("/")`. Protocol-relative URLs (`//evil.com`, and likely `/\evil.com`) satisfy this and are sent verbatim to `c.redirect(...)`, so a post-login redirect can land on an attacker domain. The session token is **not** appended to web redirects (only to native-scheme deep links), so this is a phishing / OAuth-flow-abuse vector, not token theft.
- **Fix:** Reject targets that begin with `//` or `/\`; resolve against a fixed base and confirm the resulting origin is allow-listed before redirecting.

### 3. [MEDIUM] No HTTP security headers (all origins)
Verified missing on `codecollective.us/`, `/p/`, the `/api/...` responses, and `id.codecollective.us`: `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.
- **Risk:** Login/identity pages are framable (clickjacking); no HSTS (SSL-strip on first visit); MIME sniffing; no CSP defense layer for a financial/governance app.
- **Fix:** Add headers at the Cloudflare Worker/edge: HSTS w/ `includeSubDomains; preload`, a CSP (default-src 'self' + the known asset/API origins), `X-Frame-Options: DENY` (or CSP `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, a least-privilege `Permissions-Policy`.

### 4. [MEDIUM, latent] Privilege claims live in user-writable `identity_data`
`org-worker` `adminUser()` grants admin if `identity_data.is_admin`/`is_sysadmin`/`roles` say so (`src/index.ts:333`). PIdP stores `identity_data` per website-user and self-registration accepts a caller-supplied `identity_data`. **Currently not exploitable:** `validateIdentityData` (`normalize.ts:399`) rejects unknown fields, and the default `user_schema` (+ `SYSTEM_SCHEMA_FIELDS`) contains only benign profile fields — so `{roles:["admin"]}` is rejected (422). The risk is structural: there is no separation between user-editable profile data and authorization claims. If anyone ever adds a `roles`/`is_admin` field to a website schema, self-registration becomes admin escalation.
- **Fix:** Source admin/role state from a server-only store (env allow-list or a dedicated `roles` table the user can't write), never from `identity_data`. Explicitly strip `roles`/`is_admin`/`is_sysadmin` from all user-supplied identity payloads.

### 5. [LOW] Public data exposure
`/api/org/api/network/users/public` returns internal user UUIDs (the same IDs used as `target_user_id` for connection requests). `/api/governance/motions` is fully world-readable and unthrottled (intentional transparency, but anonymous + no rate limit). Public org/event directories return large JSON (~200 KB) anonymously.
- **Fix:** Confirm the directory is opt-in; consider exposing slugs rather than raw UUIDs; add edge rate limiting to anonymous list endpoints.

### 6. [LOW] Non-constant-time secret comparison
Ingest token check `provided !== configuredToken` (`org-worker/src/index.ts:1841`), the smoke-secret check, and `verifyPassword`'s `base64Url(bits) === hashRaw` (`crypto.ts:89`) use plain comparison. Network timing attacks are impractical here, but use a constant-time compare for secrets/MACs.

### 7. [INFO] CORS
`/api/org/*` returns `access-control-allow-origin: *` without credentials — acceptable for a Bearer-token API (an attacker site can't obtain the victim's token), but broad. Handling is inconsistent (governance endpoints emit no ACAO). PIdP correctly does **not** reflect arbitrary origins with `allow-credentials` (verified with a forged `Origin`). Standardize a per-service CORS policy.

### 8. [INFO] Accessibility (login page only)
axe-core: one **serious** color-contrast violation (a link) and a missing level-one heading; no meta description. Otherwise clean (`lang`, title, viewport, `main` landmark, image alt all present). The authenticated app was not assessed.

---

## What's solid (verified)
- **Auth crypto:** PBKDF2-SHA256 @ 210k iterations w/ random salt; HS256 JWT with real signature verification, `exp` enforced, and **no `alg:none` bypass** (header alg is ignored). `/auth/me` re-reads `identity_data` from the DB rather than trusting JWT claims.
- **Cookies:** session + OAuth-state cookies are `HttpOnly; Secure; SameSite=Lax`; OAuth uses a state cookie (CSRF) and PKCE on code exchange.
- **API authorization:** ~18 protected endpoints (`accounts`, `ubi`, `stocks`, `portfolio`, `transactions`, `admin`, `system`, `scans`, `insurance`, `notifications`, …) all return `401 Authentication required` when anonymous. Admin routes return `403` without admin.
- **SQL:** parameterized `.bind()` throughout; the two dynamic `SET` clauses use code-whitelisted column names. No injection found.
- **Secrets:** none in the client JS bundle or committed Wrangler config (SECRET_KEY, OAuth secrets, ingest token are Worker secrets).

## Suggested remediation order
1. Disable `/auth/smoke-token` in production (Finding 1).
2. Add security headers at the edge (Finding 3).
3. Fix the open-redirect `next` validation (Finding 2).
4. Decouple admin/role authorization from `identity_data` (Finding 4).

## To extend to authenticated testing
The bulk of the portal (UBI, stock market, governance voting, finance ledger, tax, insurance UI/APIs) needs a session. Provide a throwaway portal test login, or enable the smoke mechanism in a **non-prod** environment, and the live audit can be driven through the same Selenium grid — there is already a working harness at `portal/web/scripts/selenium-chat-smoke.py` that uses the smoke-token path.
