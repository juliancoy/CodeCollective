# Agent deployment notes

This repository has one canonical Cloudflare frontend deployment:

- `codecollective-site` is the main site. Its build script copies the legacy static site into `.cloudflare/site`, builds the sibling OrgPortal checkout with a `/p/` base, embeds that build at `/p/`, and also builds `r8-rowhome` at `/r8-rowhome/`.

The former `codecollective-portal` standalone Worker was deleted on 2026-09-09. Do not recreate it. The only supported portal URL is `https://codecollective.us/p/`.

The root `README.md` summarizes the current frontend deployment. Use the more detailed validation and handoff requirements in this file when deploying.

## OrgPortal checkout

OrgPortal is not vendored in CodeCollective. Keep a sibling checkout at `../OrgPortal`, or set `ORGPORTAL_DIR` to the intended OrgPortal repository path before building or deploying:

```bash
git status --short --branch
git -C ../OrgPortal status --short --branch
git -C r8-rowhome status --short --branch
git submodule status
git ls-tree HEAD r8-rowhome
```

`r8-rowhome/` remains a Git submodule. A leading `+` in `git submodule status`, or `M r8-rowhome` in the root status, means the checked-out commit differs from the root pointer. Do not run `git submodule update`, reset, or switch commits just to make the tree clean: that can silently deploy an older or different product version. Establish which workspace state the user wants and deploy that exact state. Preserve unrelated user changes.

At the deployment performed on 2026-09-09, the requested workspace state was deliberately deployed as checked out:

- portal checkout: `0a8a08c0bee7a362193022d31eed2d1889b85b68`
- root-recorded portal pointer: `3a56548c7761ecc6ef08c5e5b908e15595e4c036`
- r8-rowhome checkout: `0378b74d928efe8138202c36b6ff38cc05cf6b3f`
- root-recorded r8-rowhome pointer: `52a73c2314d7ddbbafad698aafa46d6f072c7d12`

Those hashes document that deployment; they are not instructions to force future checkouts back to those versions. New OrgPortal changes should be committed and pushed in the OrgPortal repository itself. CodeCollective should not carry a submodule pointer for OrgPortal.

## Validation and deployment

Confirm Wrangler authentication before deployment:

```bash
npx wrangler --version
npx wrangler whoami
```

Run the relevant tests:

```bash
npm --prefix ../OrgPortal/web test -- --run
node --test cloudflare/*.test.mjs
npm --prefix r8-rowhome test -- --run
```

Rebuild and deploy the main site so its `/p/` bundle is generated from the checked-out portal commit:

```bash
./cloudflare/scripts/build_cloudflare_site.sh
npx wrangler deploy --dry-run
npx wrangler deploy
```

Do not deploy OrgPortal web as a separate frontend from this repository.

If changes touch `../OrgPortal/org-worker`, `../OrgPortal/chat-worker`, or `../OrgPortal/pidp/serverless`, treat their migrations, secrets, tests, and Worker deployments as separate backend work. Do not infer authorization to migrate a production D1 database merely from a request to deploy the site and portal frontend.

## Live checks

After deploying, verify all three URLs return HTTP 200 and that the asset referenced by `/p/` also loads:

- `https://codecollective-site.jcloiacon.workers.dev/`
- `https://codecollective.us/`
- `https://codecollective.us/p/`

Record the main-site Wrangler version ID in the handoff response. The standalone frontend was retired and deleted on 2026-09-09 at portal commit `b01dffaf08059fed0b4232e302c91dc3ac5d4f5d`; do not recreate it unless the user explicitly reverses that decision. The resulting main-site version was `525ee96c-6b11-4539-9657-a89999c3da71`.
