# Agent deployment notes

This repository has one canonical Cloudflare frontend deployment:

- `codecollective-site` is the main site. Its build script copies the legacy static site into `.cloudflare/site`, builds `portal/web` with a `/p/` base, embeds that build at `/p/`, and also builds `r8-rowhome` at `/r8-rowhome/`.
- `codecollective-portal` is retired as a frontend deployment. It is a lightweight permanent redirect to `https://codecollective.us/p/`, configured by `wrangler.portal-redirect.jsonc`. Keep it only for old links while traffic is observed; it may be deleted later once no clients depend on it.

The root `README.md` summarizes the current frontend deployment. Use the more detailed validation, submodule, and handoff requirements in this file when deploying.

## Critical submodule check

`portal/` and `r8-rowhome/` are Git submodules. Before building or deploying, always compare each checked-out submodule commit with the commit recorded by the root repository:

```bash
git status --short --branch
git submodule status
git -C portal status --short --branch
git -C r8-rowhome status --short --branch
git ls-tree HEAD portal r8-rowhome
```

A leading `+` in `git submodule status`, or `M portal`/`M r8-rowhome` in the root status, means the checked-out commit differs from the root pointer. Do not run `git submodule update`, reset, or switch commits just to make the tree clean: that can silently deploy an older or different product version. Establish which workspace state the user wants and deploy that exact state. Preserve unrelated user changes.

At the deployment performed on 2026-09-09, the requested workspace state was deliberately deployed as checked out:

- portal checkout: `0a8a08c0bee7a362193022d31eed2d1889b85b68`
- root-recorded portal pointer: `3a56548c7761ecc6ef08c5e5b908e15595e4c036`
- r8-rowhome checkout: `0378b74d928efe8138202c36b6ff38cc05cf6b3f`
- root-recorded r8-rowhome pointer: `52a73c2314d7ddbbafad698aafa46d6f072c7d12`

Those hashes document that deployment; they are not instructions to force future checkouts back to those versions.

## Validation and deployment

Confirm Wrangler authentication before deployment:

```bash
npx wrangler --version
npx wrangler whoami
```

Run the relevant tests:

```bash
npm --prefix portal/web test -- --run
node --test cloudflare/*.test.mjs
npm --prefix r8-rowhome test -- --run
```

Rebuild and deploy the main site so its `/p/` bundle is generated from the checked-out portal commit:

```bash
./cloudflare/scripts/build_cloudflare_site.sh
npx wrangler deploy --dry-run
npx wrangler deploy
```

Do not deploy `portal/web` as a separate frontend. If the legacy redirect changes, validate and deploy only the redirect Worker:

```bash
npx wrangler deploy --config wrangler.portal-redirect.jsonc --dry-run
npx wrangler deploy --config wrangler.portal-redirect.jsonc
```

If changes touch `portal/org-worker`, `portal/chat-worker`, or `portal/pidp/serverless`, treat their migrations, secrets, tests, and Worker deployments as separate backend work. Do not infer authorization to migrate a production D1 database merely from a request to deploy the site and portal frontend.

## Live checks

After deploying, verify the first three URLs return HTTP 200, the asset referenced by `/p/` also loads, and the legacy Worker returns HTTP 308 with a `Location` under `https://codecollective.us/p/`:

- `https://codecollective-site.jcloiacon.workers.dev/`
- `https://codecollective.us/`
- `https://codecollective.us/p/`
- `https://codecollective-portal.jcloiacon.workers.dev/`

Record the Wrangler version IDs in the handoff response. The last full standalone portal version was `51779626-05f9-455f-859b-fbf86884d53d`; do not restore it unless the user explicitly reverses the retirement decision.
