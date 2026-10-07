# Same-URL development preview

Sign in to LifeTech or the shared portal, open the user avatar menu, and choose
**App version → Development preview**. Choose **Deployed app** to return.
The page reloads at exactly the same URL, including its query and fragment.
The selection is saved per browser and hostname for 90 days.

Only frontend assets change. Organization, membership, chat, and identity
requests continue through the existing tenant APIs and permission checks. The
menu is a frontend preference, not an authorization mechanism. Development pages
show a banner explaining that account actions use live services.

The development assets live in the private `codecollective-site-preview` Worker.
`workers_dev = false`, `preview_urls = false`, and no custom routes keep it off
the public Internet. The deployed frontends use Cloudflare service bindings to
fetch its assets without forwarding session cookies or bearer tokens. It has no
production database, bucket, queue, or API bindings. Direct API/auth requests
are rejected. This setup needs ordinary Workers deployment permission; it does
not need Cloudflare Access application administration.

Development responses are private/no-store and noindex. HTML responses vary by
Cookie so one browser's selection does not affect another. Hashed assets,
site branding, and matching web update manifests are included for
root-mounted portals. Preview manifests do not advertise Android releases.

## Refresh development without changing the deployed app

Keep sibling OrgPortal and BmoreMedTech checkouts, then run from CodeCollective:

```sh
./cloudflare/scripts/deploy_web_preview.sh
```

The command reuses the canonical frontend build, adds LifeTech assets, tests the
Worker, and deploys only `wrangler.preview.toml`. The deployed app's assets and
backends are not published by this command.

Existing ignored `.env.cloudflare` supplies `CLOUDFLARE_ACCOUNT_ID` and
`CLOUDFLARE_API_TOKEN`; set `CLOUDFLARE_ENV_FILE` to use another file. Credentials
are loaded into the deployment process without being printed or copied into
frontend assets. GitHub Actions uses the equivalent repository secrets.

Production frontend configuration binds `DEV_ASSETS` to the private Worker.
The shared selection/routing implementation lives in `OrgPortal/web/deployment.mjs`.
LifeTech keeps its own static frontend routes; OrgPortal and portal tenant hosts
use the shared root portal bundle.

## CI and testing

`.github/workflows/web-preview.yml` supports manual deployment and CodeCollective
main-branch updates after the workflow is pushed. Changes in sibling repositories
are picked up at the next preview deployment; run the workflow manually after
an OrgPortal or LifeTech push. No additional Git branch is required.

Authenticated browser tests use the isolated local Docker fixture stack.
Production browser verification remains read-only and unauthenticated. Switching
frontends does not create a hosted fixture backend or sandbox account data.
