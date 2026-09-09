# MedTech portal domain

`community.medtech.social` is a Cloudflare Workers Custom Domain bound directly
to the production `codecollective-site` Worker. The binding is managed through
the Cloudflare Workers Domains API, alongside the existing community domains.
It shares the same portal assets and services as `/p/` on the main site.

The Worker redirects `/` to `/p/` on the same hostname. The portal selects the
Baltimore MedTech profile from that hostname, including for direct links and
fresh browser sessions. Public MedTech member links use the custom domain.

Authentication uses the existing PIdP Worker. `PORTAL_AUTH_ORIGINS` includes
`https://community.medtech.social`; `deploy.sh` retains this configuration.
The Google and GitHub provider callback registrations remain on the identity
service. Signed OAuth state records the allowed portal origin. The identity
callback returns the provider's one-use authorization code to the initiating
portal before exchanging it, requiring the portal's original state cookie.
Session tokens are never included in browser redirect URLs. The site Worker
removes the identity service's cookie Domain attribute on MedTech `/pidp/`
responses, preserving Secure, HttpOnly, and SameSite cookie attributes.

Deploy PIdP before the site when changing this flow. Preserve existing PIdP
variables and secrets; the base serverless config contains development defaults.
The public `baltimore-medtech` Worker remains bound to `medtech.social`.

Portal builds use `VITE_PIDP_BASE_URL=/pidp` so sign-in stays on the initiating
hostname. After a verified manual release, `[skip deploy]` in the parent commit
message keeps GitHub build checks running without deploying the services again.

The MedTech login page includes a small **Clear local cache** link. Its
`/p/clear-cache` response sends `Clear-Site-Data: "cache"` and redirects back to
the login page, retaining the query parameters. It clears the current origin's
browser file cache; cookies, preferences, and browser connections are unaffected.

Upcoming-event pictures use `imageUrl` from the published calendar JSON, falling
back to `orgImageUrl`. Relative paths resolve against the published feed URL on
Code Collective. The public calendar and member event list hide unavailable
images while retaining event details.

## Google callback 403 investigation

On 2026-09-09 UTC, the affected browser returned 403 even for the public `/health`
endpoint. The user confirmed that the same endpoint returned `{"status":"ok"}`
in a private window, isolating the difference to the normal browser session.
The user then completed a real Google sign-in through `community.medtech.social`
in that private window. Normal-window recovery remains unverified; fully
restarting the browser is the next check for stale connection state.

A temporary Browser Integrity Check exception did not resolve the failure. Both
the exception and its newly created empty ruleset were removed, restoring the
prior firewall configuration. No WAF exception is required by this deployment.

Docker-backed Chrome checks confirm callback redirects, signed-state validation,
and rejection of a missing initiating cookie. Separate IPv4, IPv6, and HTTP/2
checks reach `/health`. Forcing an HTTP/2 identity request onto a TLS connection
opened for the main hostname reproduces an empty 403 before the Worker runs,
but this does not prove the affected browser used that connection pattern.
Cloudflare documents early [SNI mismatch 403 responses](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-403/).

Focused checks, run inside Docker:

- Portal: the `portalFeatures`, `pidp`, and `medtechCommunity` Vitest suites and
  `npm run build` in `portal/web`.
- Identity: `npm run typecheck` and `npm test` in `portal/pidp/serverless`.
- Site routing and cookies: `node --test cloudflare/medtech-domain.test.mjs`.
- Release: shared site build, Wrangler dry runs, and desktop/mobile browser
  checks on the HTTPS custom domain.
