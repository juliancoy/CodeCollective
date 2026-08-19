# Scraping Policy

## Goal
Keep event ingestion reliable without getting blocked, banned, or causing undue load on source websites.

## Required Standards
- Identify as a bot:
  - Use `CodeCollectiveBot/1.0 (+https://github.com/juliancoy/CodeCollective)` or a compatible transparent UA.
- Rate limit by host:
  - Minimum 1 second between requests to the same host.
  - Use per-domain overrides in `data/scrape_host_policy.json` for stricter pacing on sensitive hosts.
- Timeouts:
  - Every request must set a timeout (default 30s).
- Retries:
  - Retry transient failures (`429`, `500`, `502`, `503`, `504`) with exponential backoff.
  - Respect `Retry-After` when present.
- TLS:
  - Do not disable certificate verification (`verify=False` is disallowed).
- Robots:
  - Perform robots.txt-aware preflight checks before fetches (enabled in shared client).
- Conditional requests:
  - Revalidate cached responses with `ETag` / `If-None-Match` and `Last-Modified` / `If-Modified-Since` when the source supports them.
  - Reuse cached bodies after `304 Not Modified` responses instead of downloading and reparsing unchanged content.

## Implementation Rule
- New or updated scrapers should use shared helpers in `http_client.py`:
  - `build_session(...)`
  - `polite_get(...)`
  - Do not call `requests.get(...)` directly in new scraper code.

## Source Respect and Safety
- Prefer official feeds/APIs (ICS, JSON-LD, public APIs) over brittle DOM scraping.
- Keep scraping cadence moderate; avoid unnecessary repeated fetches.
- Prefer cached/conditional fetch paths when available.
- If a source repeatedly returns `403`/`429`, back off and avoid hammering.

## Operational Guardrails
- Track scrape failures by source and host.
- Disable or cool down sources with persistent blocking patterns.
- Re-enable only after validating source stability.

## Professionalization Backlog
1. Add centralized scrape telemetry dashboards (status code, latency, fail rate, cache revalidation rate).
2. Add per-domain failure budgets and automatic cooldown windows.
3. Continue migrating legacy scraper modules that still call `requests.get(...)` directly to the shared polite HTTP client.
