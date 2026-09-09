# Agent deployment notes

This repository has two related Cloudflare frontend deployment targets. Treat them as separate deployments built from the same `portal/web` source:

- `codecollective-site` is the main site. Its build script copies the legacy static site into `.cloudflare/site`, builds `portal/web` with a `/p/` base, embeds that build at `/p/`, and also builds `r8-rowhome` at `/r8-rowhome/`.
- `codecollective-portal` is the standalone portal Worker. It builds `portal/web` for `/` and deploys it independently.

The root `README.md` still contains older GitHub Pages/AWS wording. For the current Cloudflare deployment, use the repository's Wrangler configurations and scripts described here.

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

Deploy the standalone portal first. The checked-in script deploys only `portal/web`; it does not deploy the org, chat, or PIdP backend Workers.

```bash
./portal/scripts/deploy_portal.sh --skip-install -- --dry-run
./portal/scripts/deploy_portal.sh --skip-install --skip-build
```

Then rebuild and deploy the main site so its `/p/` bundle is generated from the same portal checkout:

```bash
./cloudflare/scripts/build_cloudflare_site.sh
npx wrangler deploy --dry-run
npx wrangler deploy
```

Do not deploy the standalone portal after the root build with `--skip-build`: the root build leaves `portal/web/dist` configured for `/p/`, whereas the standalone portal needs a fresh `/` build. The sequence above avoids that mismatch.

If changes touch `portal/org-worker`, `portal/chat-worker`, or `portal/pidp/serverless`, treat their migrations, secrets, tests, and Worker deployments as separate backend work. Do not infer authorization to migrate a production D1 database merely from a request to deploy the site and portal frontend.

## Live checks

After deploying, verify all of these return HTTP 200 and that the asset referenced by `/p/` also loads:

- `https://codecollective-site.jcloiacon.workers.dev/`
- `https://codecollective.us/`
- `https://codecollective.us/p/`
- `https://codecollective-portal.jcloiacon.workers.dev/`

Record the Wrangler version IDs in the handoff response. The 2026-09-09 deployment produced main-site version `0f7759c1-989a-4ede-a775-5b34706a9e2c` and standalone-portal version `51779626-05f9-455f-859b-fbf86884d53d`.
