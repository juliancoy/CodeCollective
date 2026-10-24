# USAJOBS Data Pipeline (R2 Shards)

This pipeline keeps refined USAJOBS data out of git and publishes sharded JSON to Cloudflare R2.

## Local deployment

The workspace `python run.py` starts CodeCollective's local site and USAJOBS API
at http://localhost:8877/usa/. The site container runs `python3 run.py serve`
from the CodeCollective checkout and reads its bind-mounted
`usa/data/publish/jobs/latest.json`, versioned manifests, and gzip shards.
The History dropdown lists saved snapshots by retrieval date and job count.
Switching snapshots retains filters and loads every page from the selected version.
`/api/jobs/versions` lists the locally stored snapshots; no missing history is
downloaded automatically. Both `/api/jobs/meta` and `/api/jobs` read local files; neither proxies production
nor calls USAJOBS. The displayed retrieval date belongs to that local snapshot.

To restart only CodeCollective's site from this repository:

```bash
python run.py start --no-r8 --no-datacenters
```

A missing local dataset produces an error rather than a remote fallback. Build
shards using the commands below when preparing a new local snapshot.

## Local build of shards

```bash
./usa/refresh_usajobs_search.sh
python usa/shard_jobs.py \
  --input usa/data/usajobs-lite.json.gz \
  --output-root usa/data/publish \
  --prefix jobs \
  --shard-size 500
```

Output keys are written under `usa/data/publish/jobs/`:

- `jobs/latest.json`
- `jobs/vYYYYMMDDTHHMMSSZ/manifest.json`
- `jobs/vYYYYMMDDTHHMMSSZ/shards/state=<STATE>/page=0001.json.gz`

## Publish to R2

Required env vars:

- `R2_BUCKET`
- `R2_ENDPOINT_URL` (example: `https://<accountid>.r2.cloudflarestorage.com`)
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Publish and keep last 30 versions:

```bash
python usa/publish_to_r2.py \
  --input-root usa/data/publish \
  --prefix jobs \
  --keep-versions 30
```

## Worker API (served by `cloudflare/worker.js`)

- `GET /api/jobs/meta` (latest manifest)
- `GET /api/jobs/meta?version=vYYYYMMDDTHHMMSSZ`
- `GET /api/jobs?state=MD&page=1`
- `GET /api/jobs?state=ALL&page=1`

## GitHub Actions automation

Workflow: `.github/workflows/update-usajobs.yml`

Collection is paused. The scheduled trigger has been removed and the workflow
is disabled in GitHub Actions. The tracker remains at `/usa/` with its existing
data, but is no longer linked from Projects. To collect again, explicitly
re-enable the workflow and run it manually.

Set these repository secrets:

- `USAJOBS_API_KEY`
- `USAJOBS_USER_AGENT`
- `USAJOBS_EMAIL`
- `R2_BUCKET`
- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

## Terms of Service review (2026-10-24)

Reviewed the October 9, 2026 email “Update: Further Revisions to the USAJOBS
API Terms of Service” sent to julian@codecollective.us against the collectors,
tracker, R2 publishing, and encrypted backup usage. The revised text is also
published at https://developer.usajobs.gov/apirequest/index.

- Section 2 expressly permits copying, caching, adapting, analysis, publishing,
  and redistribution of public Search, Historic JOA, Announcement Text, and
  code-list data, including commercial use, without prior OPM approval.
  Existing public datasets, feeds, and backups do not require removal.
  This permission excludes content separately marked with a legal or third-party
  restriction; review accompanying notices before adding new endpoints or data.
- Attribution, official-announcement links, retrieval dates, and non-affiliation
  notices are encouraged. The tracker supplies these and explicitly describes its
  normalized data as cached and potentially outdated. A cached open/closed status
  is not a live verification. Applications follow the official announcement's
  instructions; this tracker neither collects nor submits them.
- Only public endpoints are used. No applicant profiles, applications, account
  data, government seals, or claims of federal endorsement are part of the tracker.
- Credentials stay in environment variables, ignored local `.env.usajobs`, or
  GitHub secrets. Static builds exclude `.env*`; never publish API credentials or
  share them with unauthorized users. Keep registration/contact details current.
  Report suspected unauthorized credential use or API security incidents promptly
  to access@usajobs.gov. Registration accuracy and provider-side account activity
  must be checked by the account holder; source review cannot establish them.
- Collectors stop on HTTP 429 or an explicit `Retry-After` response, preserving
  existing caches. Wait until the provider's pause ends before rerunning. Other
  transient server/network failures use bounded retries; authentication and
  authorization failures are not retried. Do not rotate keys or shard around
  throttling. Search uses at most 500 results per page and 10,000 per query;
  narrower queries partition results within those documented limits.
- The tracker loads version-pinned R2 API shards and uses `source_fetched_at`
  for its retrieval date, rather than the shard build time or a missing static file.
- Collection remains paused; this review does not re-enable the workflow.

Checks: `python -m unittest discover -s tests -p 'test_usajobs_compliance.py'`
and `node --test tests/usajobs_navigation.test.cjs`.
