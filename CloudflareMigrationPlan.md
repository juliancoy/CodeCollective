# Cloudflare Migration Plan

This plan migrates Code Collective toward Cloudflare in two tracks:

1. First, launch the serverless Cloudflare PIdP as an isolated identity service at `id.codecollective.us`.
2. Then migrate the public `codecollective.us` site and integrated portal surface to Cloudflare Workers static assets.

The first production milestone is intentionally narrow: keep the current website stable, deploy only the serverless PIdP on Cloudflare, and point the existing Cloudflare site/portal integration at that identity origin.

## Current State

- The root website is primarily static HTML, CSS, JavaScript, and generated data.
- Root Cloudflare deployment already exists:
  - `wrangler.toml`
  - `cloudflare/worker.js`
  - `scripts/build_cloudflare_site.sh`
  - `deploy.sh`
- The root Worker serves:
  - legacy static site assets from `.cloudflare/site`
  - the portal SPA at `/p/`
  - `/api/governance/*` proxied to `GOVERNANCE_API_ORIGIN`
  - `/pidp/*` proxied to `PIDP_API_ORIGIN` with the `/pidp` prefix stripped
  - jobs and vacants API data from R2 bindings
- The portal is a submodule at `portal/`.
- The serverless PIdP implementation exists at `portal/pidp/serverless/` and uses:
  - Cloudflare Workers
  - TypeScript and Hono
  - D1 for relational identity data
  - R2 for avatar object storage
  - Worker secrets for signing and OAuth credentials
- Existing portal docs:
  - `portal/docs/deployment/CLOUDFLARE_PIDP_DEPLOYMENT.md`
  - `portal/docs/deployment/CLOUDFLARE_FULL_MIGRATION.md`
  - `portal/pidp/serverless/README.md`

## Target Architecture

### Phase 1 Target

- `id.codecollective.us` serves the serverless PIdP Worker.
- `codecollective.us` remains on the current production hosting path.
- Existing portal and website integrations use `https://id.codecollective.us` as the PIdP API origin.
- The root Cloudflare Worker, when deployed for testing, sets:
  - `PIDP_API_ORIGIN=https://id.codecollective.us`
  - `PIDP_PROXY_ORIGIN=https://pidp-codecollective.jcloiacon.workers.dev` for the optional `/pidp/*` compatibility proxy
  - `GOVERNANCE_API_ORIGIN=<current governance backend origin>`
- The public site can continue exposing `/pidp/*` as a compatibility proxy if needed, but new code should prefer the canonical `https://id.codecollective.us` identity origin.

Current deployment note: the Worker is live at `https://id.codecollective.us`, with `https://pidp-codecollective.jcloiacon.workers.dev` retained as the fallback Worker URL.

## CI/CD Deployment Scheme

Production deploys should flow through GitHub Actions, not a developer laptop:

1. Pull requests run build and test checks without deploying.
2. Pushes to `main` run the same checks and deploy to Cloudflare.
3. Manual runs of the `Cloudflare Deploy` workflow can deploy `all`, `site`, `pidp`, or run `checks-only`.
4. Cloudflare routes and DNS are treated as standing infrastructure:
   - `codecollective.us/*` routes to `codecollective-site`
   - `id.codecollective.us/*` routes to `pidp-codecollective`

Required GitHub repository or environment secrets:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
PROD_GOVERNANCE_API_ORIGIN
```

`PROD_GOVERNANCE_API_ORIGIN` can be omitted only if the default `https://portal.arkavo.org` remains correct. PIdP OAuth secrets stay in Cloudflare Worker secrets and are not stored in GitHub Actions.

Emergency local deploy commands remain available:

```bash
./deploy.sh --component all --target prod
./deploy.sh --component site --target prod
./deploy.sh --component pidp
```

The root deploy script generates a temporary production `portal/pidp/serverless/wrangler.jsonc` for local PIdP deployments, runs the serverless deployment helper, and restores the generic checked-in config afterward.

### Full Migration Target

- `codecollective.us` and `www.codecollective.us` are served by the root Cloudflare Worker.
- Static site assets are built into `.cloudflare/site`.
- Portal SPA is mounted at `/p/`.
- Serverless PIdP remains at `id.codecollective.us`.
- Governance backend remains separately hosted until it is explicitly migrated or replaced.
- Large generated datasets are served through R2-backed Worker API routes, not as oversized static assets.

## Phase 0: Readiness Audit

1. Confirm Cloudflare account, zone, and Wrangler access.
2. Confirm `codecollective.us` is present as a Cloudflare zone before DNS cutover.
3. Confirm no one is relying on Git branch creation for this migration; keep all work on the current branch.
4. Resolve or document the dirty `portal` submodule before deployment so the deployed code can be reproduced.
5. Inventory current production URLs:
   - `https://codecollective.us/`
   - `https://www.codecollective.us/`
   - current portal entry point
   - current PIdP origin
   - current governance backend origin
6. Decide the canonical identity host:
   - recommended: `id.codecollective.us`
   - acceptable alternative: `pidp.codecollective.us`

## Phase 1: Deploy Serverless PIdP at `id.codecollective.us`

### 1. Configure Cloudflare Resources

From `portal/pidp/serverless/`:

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create or select the production D1 database:

   ```bash
   npx wrangler d1 create pidp
   ```

3. Create or select the avatar R2 bucket:

   ```bash
   npx wrangler r2 bucket create pidp-avatars
   ```

4. Update `portal/pidp/serverless/wrangler.jsonc`:

   - `name`: use a production name such as `pidp-codecollective`
   - `ENV`: `production`
   - `APP_NAME`: `Code Collective ID`
   - `ALLOWED_ORIGINS`: include `https://codecollective.us`, `https://www.codecollective.us`, and any portal preview hosts
   - `FRONTEND_REDIRECT_URL`: set to the portal callback route
   - `GOOGLE_REDIRECT_URI`: `https://id.codecollective.us/auth/google/callback`
   - `GITHUB_REDIRECT_URI`: `https://id.codecollective.us/auth/github/callback`
   - `d1_databases[0].database_id`: set to the Cloudflare D1 database id
   - `r2_buckets[0].bucket_name`: set to the avatar bucket

### 2. Set Required Secrets

Set production secrets with Wrangler:

```bash
npx wrangler secret put SECRET_KEY
npx wrangler secret put GOOGLE_CLIENT_ID
npx wrangler secret put GOOGLE_CLIENT_SECRET
npx wrangler secret put GITHUB_CLIENT_ID
npx wrangler secret put GITHUB_CLIENT_SECRET
```

If OAuth is not required for the first launch, deploy with local email/password flows first and leave OAuth disabled until callback URLs are registered with Google and GitHub.

### 3. Apply Database Migrations

Run:

```bash
npm run typecheck
npm test
npm run db:migrate:remote
```

Then verify tables through Wrangler:

```bash
npx wrangler d1 execute pidp --remote --command "SELECT name FROM sqlite_master WHERE type='table';"
```

### 4. Deploy Worker

Run:

```bash
npm run deploy:status
npm run deploy:serverless -- --dry-run
npm run deploy:serverless
```

Add a Cloudflare route or custom domain for:

```txt
id.codecollective.us/*
```

The exact binding can be done through Cloudflare Workers custom domains or a proxied DNS record plus Worker route, depending on the account setup.

### 5. Validate PIdP

Smoke checks:

```bash
curl -i https://id.codecollective.us/health
curl -i https://id.codecollective.us/.well-known/jwks.json
curl -i https://id.codecollective.us/auth/me
```

Expected results:

- health/configuration endpoint returns `200`
- unauthenticated `/auth/me` returns `401`
- profile, registration, login, token, and website CRUD routes match the serverless README expectations

Known parity gaps from `portal/pidp/serverless/README.md` must be handled before replacing the existing Python PIdP for existing users:

- RS256/JWKS key publishing may need completion depending on consumers.
- Existing Python bcrypt password hashes are not directly compatible with the new PBKDF2-SHA256 hashing.
- Fernet-compatible encrypted JSON migration is not yet implemented.
- Server-rendered Jinja console parity is not yet implemented.

For an initial launch, choose one of these identity migration strategies:

- new identity namespace for `codecollective.us` users
- forced password reset for migrated users
- add Worker-compatible bcrypt/argon2 verification before cutover
- keep legacy PIdP as fallback until migration tooling is complete

## Phase 2: Integrate Current Website and Portal With `id.codecollective.us`

### 1. Root Worker Integration

Update deployment environment for root `deploy.sh`:

```bash
PROD_PIDP_API_ORIGIN=https://id.codecollective.us
DEV_PIDP_API_ORIGIN=https://id.codecollective.us
```

Keep:

```bash
PROD_GOVERNANCE_API_ORIGIN=<current governance backend origin>
DEV_GOVERNANCE_API_ORIGIN=<current dev governance backend origin>
```

Deploy only to the dev Worker first:

```bash
./deploy.sh --target dev
```

Validate:

```bash
curl -i https://<dev-worker>.workers.dev/
curl -i https://<dev-worker>.workers.dev/p/
curl -i https://<dev-worker>.workers.dev/p/constituent/dashboard
curl -i https://<dev-worker>.workers.dev/pidp/auth/me
```

Expected `/pidp/auth/me` result is `401` without a login token.

### 2. Portal Build Integration

Confirm the portal frontend build points at the correct PIdP base:

- If the portal uses the root Worker proxy, use `/pidp`.
- If the portal talks directly to identity, use `https://id.codecollective.us`.

Preferred steady state:

```txt
VITE_PIDP_BASE_URL=https://id.codecollective.us
VITE_PIDP_APP_SLUG=code-collective
```

Use the proxy only as compatibility glue for existing deployed frontend bundles.

### 3. OAuth Provider Integration

Register production callback URLs:

```txt
https://id.codecollective.us/auth/google/callback
https://id.codecollective.us/auth/github/callback
```

Register any dev callback URLs separately, for example:

```txt
https://dev.id.codecollective.us/auth/google/callback
https://dev.id.codecollective.us/auth/github/callback
```

Do not reuse production OAuth secrets in development if avoidable.

### 4. CORS and Cookie Review

Confirm serverless PIdP allows:

- `https://codecollective.us`
- `https://www.codecollective.us`
- current Worker preview URL
- local development URLs only in dev environments

Confirm any cookie-based flows use:

- `Secure`
- `HttpOnly` where possible
- `SameSite=Lax` or stricter unless cross-site OAuth callback behavior requires otherwise
- domain scoping appropriate for `id.codecollective.us` versus `codecollective.us`

## Phase 3: Stabilize and Observe

1. Enable Cloudflare Worker observability for PIdP.
2. Add uptime checks for:
   - `https://id.codecollective.us/health`
   - `https://codecollective.us/p/`
   - `/pidp/auth/me` compatibility proxy if retained
3. Track errors for:
   - failed logins
   - OAuth callback failures
   - D1 write failures
   - R2 avatar upload failures
   - CORS preflight failures
4. Export or snapshot D1 before any irreversible user migration.
5. Document rollback:
   - point portal config back to the legacy PIdP origin
   - redeploy root Worker with previous `PIDP_API_ORIGIN`
   - leave `id.codecollective.us` online but stop routing new users to it

## Phase 4: Full `codecollective.us` Cloudflare Migration

### 1. Build Full Site Bundle

From repo root:

```bash
./scripts/build_cloudflare_site.sh
```

This writes:

```txt
.cloudflare/site
```

Verify the bundle contains:

- `/index.html`
- `/p/index.html`
- `/r8-rowhome/index.html` if `r8-rowhome/` is present
- expected static assets
- no oversized Worker static assets

### 2. Deploy Dev Worker

Run:

```bash
PROD_PIDP_API_ORIGIN=https://id.codecollective.us \
DEV_PIDP_API_ORIGIN=https://id.codecollective.us \
./deploy.sh --target dev
```

Validate on the dev Worker URL:

- `/`
- `/about-us.html`
- `/calendar.html`
- `/newsletter/`
- `/p/`
- `/p/constituent/dashboard`
- `/r8-rowhome/`
- `/api/jobs/meta`
- `/api/vacants/meta`
- `/pidp/auth/me`

### 3. Deploy Production Worker Before DNS Cutover

Run:

```bash
PROD_PIDP_API_ORIGIN=https://id.codecollective.us \
./deploy.sh --target prod
```

Use the returned `workers.dev` URL for pre-cutover smoke testing.

### 4. Cloudflare DNS and Routing

In Cloudflare:

1. Add `codecollective.us`.
2. Confirm DNS records for:
   - `codecollective.us`
   - `www.codecollective.us`
   - `id.codecollective.us`
3. Attach Worker routes:
   - `codecollective.us/*` to the root site Worker
   - `www.codecollective.us/*` to the root site Worker
   - `id.codecollective.us/*` to the PIdP Worker
4. Set SSL/TLS mode to `Full (strict)` where origin TLS is still involved. Worker-only routes can be served directly at the edge.
5. Lower TTLs before cutover where the current DNS provider supports it.

### 5. Registrar Nameserver Cutover

At the domain registrar, replace the current nameservers with the Cloudflare nameservers for the zone.

Do not delete the old AWS S3/CloudFront deployment immediately. Keep it available for rollback until Cloudflare traffic has been stable for at least one full operational window.

### 6. Post-Cutover Validation

Validate:

```bash
curl -I https://codecollective.us/
curl -I https://www.codecollective.us/
curl -I https://codecollective.us/p/
curl -I https://codecollective.us/calendar.html
curl -I https://id.codecollective.us/health
curl -I https://codecollective.us/pidp/auth/me
```

Browser-test:

- homepage rendering
- calendar rendering and filters
- newsletter pages
- portal login route
- identity registration/login
- OAuth login, if enabled
- avatar upload, if enabled
- mobile viewport navigation

## Phase 5: Decommission and Cleanup

After stable production operation:

1. Update `README.md` so the deployment split reflects Cloudflare as the source of truth.
2. Document current Cloudflare resource names:
   - site Worker
   - dev site Worker
   - PIdP Worker
   - D1 database
   - R2 buckets
   - routes/custom domains
3. Remove or archive obsolete AWS deployment instructions only after rollback is no longer needed.
4. Decide whether to retain `/pidp/*` on `codecollective.us`:
   - keep it for compatibility if older portal bundles exist
   - remove it once all frontend code uses `https://id.codecollective.us`
5. Add CI checks for:
   - root Worker build
   - portal build
   - serverless PIdP typecheck and tests
   - smoke tests against dev Worker

## Rollback Plan

### PIdP Rollback

1. Set `PIDP_API_ORIGIN` back to the legacy PIdP origin.
2. Redeploy root Worker or portal frontend config.
3. Disable new-user entry points that depend on `id.codecollective.us`.
4. Keep the D1 database intact for investigation and possible replay.

### Full Site Rollback

1. Restore registrar nameservers to the previous Route53 nameservers.
2. Keep Cloudflare Workers deployed while DNS propagates back.
3. Verify:
   - `https://codecollective.us/`
   - `https://www.codecollective.us/`
   - portal entry point
4. Preserve Cloudflare logs from the failed migration window.

## Open Decisions

- Canonical PIdP host is `id.codecollective.us`.
- Decide whether the first launch supports only new users or migrates existing users.
- Decide whether OAuth is required for the first launch.
- Confirm governance backend hosting remains outside Cloudflare for this migration.
- Confirm whether `/p/` remains the long-term portal path on `codecollective.us`.
- Confirm whether `www.codecollective.us` should redirect to apex or serve identical content; no `www` DNS record exists currently.

## Deployment Checklist

- [x] Cloudflare zone exists for `codecollective.us`.
- [x] `id.codecollective.us` route/custom domain is configured.
- [x] PIdP D1 database created and id committed or injected into deploy config.
- [x] PIdP R2 avatar bucket created.
- [x] Required PIdP `SECRET_KEY` Worker secret set; OAuth secrets remain unset.
- [x] PIdP migrations applied remotely.
- [x] PIdP Worker deployed.
- [x] PIdP smoke checks pass.
- [x] Root Worker dev deploy uses `PIDP_API_ORIGIN=https://id.codecollective.us`.
- [ ] Portal auth flow works against serverless PIdP.
- [x] Root site Worker production deploy passes pre-cutover smoke checks.
- [x] Apex Worker route `codecollective.us/*` is active.
- [ ] AWS/legacy rollback target remains available.
- [x] Post-cutover validation passes for `/`, `/p/`, `/pidp/health`, and PIdP health/JWKS/login page.
