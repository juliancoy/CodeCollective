# USAJOBS Data Pipeline (R2 Shards)

This pipeline keeps refined USAJOBS data out of git and publishes sharded JSON to Cloudflare R2.

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

Set these repository secrets:

- `USAJOBS_API_KEY`
- `USAJOBS_USER_AGENT`
- `USAJOBS_EMAIL`
- `R2_BUCKET`
- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
