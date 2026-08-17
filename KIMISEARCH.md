# Kimi Web Research Best Practices

This document defines the operating standard for large-scale, source-backed web
research over the power-plant and data-center inventory. The objective is not to
maximize the number of populated fields. It is to produce defensible,
facility-specific findings with enough provenance to review, reproduce, and
eventually publish safely.

## 1. Architecture

Use a staged pipeline rather than one expensive model call per record:

```text
canonical inventory
        |
unresolved facet detection
        |
one facility research job
        |
K2.6 + required web search
        |
schema and evidence validation
        |
retry only for a real evidence or output gap
        |
optional K3 escalation for difficult cases
        |
append-only checkpoint
        |
review or validated promotion
        |
atomic infrastructure.json update
```

Keep collection and publication separate. Research workers may run concurrently,
but they must not write directly to `datacenters/data/infrastructure.json`. A
single promotion coordinator should serialize accepted changes into the canonical
inventory.

## 2. Unit Of Work

Use one facility per job and research all unresolved facets for that facility in
the same context. This is usually more efficient and more accurate than one query
per facet because identity, operator, location, and source discovery are shared.

Each job must include:

- Stable facility ID and exact canonical name.
- Record type, operator, address, municipality, county, and coordinates when known.
- Alternate names or former operators when known.
- Only the facets currently marked unresolved.
- Existing source records as leads, not as automatically trusted evidence.
- An input fingerprint so changed inventory records can be researched again.

Never combine multiple facilities in one model request. Similar facility names,
shared campuses, and operator portfolios make cross-record contamination likely.

## 3. Entity Resolution

Establish facility identity before accepting any substantive claim.

- Match on more than a name whenever possible: address, parcel, EIA plant ID,
  permit number, operator entity, coordinates, or campus name.
- Treat parent-company and fleet-level claims as context, not facility facts.
- Distinguish a campus from an individual building or generation plant.
- Record aliases used in searches.
- Use `insufficient` confidence when two plausible facilities cannot be separated.
- Reject output whose facility ID or canonical name does not match the requested
  target.

Do not silently transfer facts between facilities owned by the same operator.

## 4. Search Strategy

Search for evidence gaps, not generic summaries. Good searches combine the
facility identity with the agency, document type, or facet being investigated.

Preferred source order:

1. State and federal agency records.
2. County or municipal planning, zoning, permit, and meeting records.
3. Court dockets and administrative appeal records.
4. Operator filings and facility-specific operator pages.
5. Reliable reporting with named documents or attributable sources.
6. Directories and aggregators only as discovery leads.

Useful query families include:

```text
"facility name" site:mde.maryland.gov permit
"facility address" air permit
"facility name" site:planning.maryland.gov
"facility name" zoning OR site plan OR special exception
"facility name" lawsuit OR appeal OR docket
"facility name" opposition OR hearing OR testimony
"facility name" natural gas generator OR turbine OR engine
"operator legal entity" "county name" permit
```

Search alternate names when the first query is weak. Do not repeat equivalent
queries merely to satisfy a numeric search minimum. Carry prior queries and
evidence into later stages.

## 5. Negative Claims

Absence claims require special care. A failed search does not prove that a permit,
lawsuit, opposition campaign, or on-site power plant does not exist.

Use bounded language:

```text
No facility-specific lawsuit was identified in the reviewed sources as of
YYYY-MM-DD.
```

Avoid unbounded language:

```text
There is no lawsuit.
```

A defensible negative finding should identify what was searched, the relevant
agency or docket coverage, the date of review, and remaining limitations. Assign
`insufficient` or `low` confidence when source coverage is narrow.

## 6. Model Routing

Use the cheapest model that reliably completes the task.

- Primary: `kimi-k2.6`, thinking disabled, at least one real web search.
- Retry: `kimi-k2.6`, thinking disabled, only when output is malformed, facets
  remain unresolved, or an additional search is required.
- Escalation: `kimi-k3` with low reasoning only for ambiguous identity, conflicting
  sources, complex legal history, or repeated structured-output failure.

Do not retry a complete, valid, low-confidence result when the cumulative search
minimum is already met and the retry would only resynthesize the same evidence.
That spends tokens without increasing coverage.

Do retry a partial response to recover malformed or omitted facets. Preserve any
independently valid facets from the earlier response so later work is incremental.

Evaluate model routing from measured outcomes:

- Cost per accepted facet.
- Cost per reviewable facet.
- Confidence improvement by stage.
- New searches added by retry.
- Validation recovery rate.
- Rate at which retries degrade previously valid output.

Escalation should be justified by better evidence or validity, not by model prestige.

## 7. Structured Output Contract

Every requested facet must contain:

```json
{
  "value": "concise inventory-ready finding",
  "confidence": "high | medium | low | insufficient",
  "basis": "what the evidence establishes and its limits",
  "sources": [
    {
      "title": "document or page title",
      "publisher": "publisher",
      "url": "https://example.gov/document",
      "document_date": "YYYY-MM-DD or null",
      "source_type": "primary government",
      "supports": "specific claim supported by this source"
    }
  ]
}
```

Validation must enforce:

- Exact facility identity.
- Requested facet names only.
- Allowed confidence values.
- Non-empty finding and substantive basis.
- At least one valid HTTP or HTTPS source per accepted facet.
- Source title, publisher, type, and support statement.
- Cumulative distinct-search minimum.
- Independent facet validation so one malformed facet does not discard others.

JSON validity is necessary but not sufficient. A well-formed unsupported claim is
still invalid.

## 8. Evidence Quality

Each citation must support the facet to which it is attached. A general operator
page cannot establish a facility-specific permit decision unless it actually names
the facility and decision.

Apply these rules:

- Prefer the final permit or decision over an application.
- Prefer the official docket over an article describing litigation.
- Preserve document dates and permit or case identifiers when available.
- Separate reported facts from analyst inference.
- Label capacity, demand, cost, employment, and workflow estimates explicitly.
- Do not treat search-result snippets as durable evidence.
- Do not invent URLs, quotations, dates, agencies, permit IDs, or docket numbers.
- Keep enough basis text for a reviewer to understand why the source supports the
  value without rerunning the model.

## 9. Confidence

Confidence describes support for the facility-specific claim, not confidence in
the model.

- `high`: direct, current, primary evidence unambiguously identifies the facility
  and supports the finding.
- `medium`: credible facility-specific evidence supports the finding, with limited
  ambiguity or incomplete coverage.
- `low`: relevant evidence exists but is indirect, old, incomplete, or weakly tied
  to the facility.
- `insufficient`: the requested fact cannot be established responsibly.

Automatic acceptance should normally require every requested facet to be at least
`medium`. Lower-confidence output remains useful for review and should not be
discarded.

## 10. Concurrency And Rate Control

Concurrency should be controlled at the facility level. A worker may make several
sequential chat and search requests for one facility.

- Start with a small pilot before increasing workers.
- Raise workers only when error rate, latency, and provider throttling remain stable.
- Keep executor capacity separate from active worker count so REST controls can
  scale within a fixed safe ceiling.
- Pause at facility or stage boundaries; do not cancel an HTTP request midway.
- Gracefully stop and checkpoint in-flight completions.
- Respect provider rate limits and exponential backoff instructions.
- Never infer safe concurrency solely from CPU utilization; this workload is
  network- and provider-limited.

More workers improve throughput only until API contention, throttling, or review
quality becomes the limiting factor.

## 11. Checkpointing And Resumption

Use append-only JSONL for research records and operational events.

Every facility record should include:

- Run ID and pipeline ID.
- Facility ID, record type, requested facets, and input fingerprint.
- Start and finish timestamps.
- Every attempted stage and its raw structured result.
- Search queries and prior queries.
- Validation failures and salvaged facets.
- Request IDs, Formula Fiber IDs, latency, retries, and token usage.
- Estimated stage and facility cost.
- Final status: `ok`, `review`, or `error`.

Resume only when both pipeline ID and input fingerprint match. Skip completed `ok`
and `review` records. Retry `error` records. Use `--force` only for a deliberate
full re-evaluation, because it can duplicate substantial spending.

Do not edit checkpoint history in place. Corrections should be new records so the
decision trail remains auditable.

## 12. Diagnostics

Operational logging must be useful without exposing secrets or bloating logs with
request bodies.

Track at minimum:

- Submitted, queued, in-flight, and processed facilities.
- Active and maximum workers.
- Facility and stage currently in flight.
- Accepted, review, and error counts.
- Throughput, elapsed time, and estimated completion time.
- Search count and searches per facility.
- HTTP retries, retry causes, and backoff time.
- Prompt, cached-input, completion, and reasoning tokens.
- Estimated cost by run, facility, and stage.
- Validation errors, partial salvage, and skipped retries.

Never log API keys, full authorization headers, encrypted search payloads, or
unnecessarily large prompts. Request and response IDs are preferable for provider
support and correlation.

Use the local endpoints while a run is active:

```bash
curl -s http://127.0.0.1:8765/status | python3 -m json.tool
```

Open the dashboard and received-data inspector at:

```text
http://127.0.0.1:8766/
```

## 13. Cost Management

Pricing changes. Store a dated pricing snapshot with each run and distinguish
provider-reported usage from estimated fees.

Before a full run:

1. Run a representative pilot that includes easy, ambiguous, and malformed cases.
2. Measure average and percentile cost per facility.
3. Measure retry and escalation frequency.
4. Forecast remaining cost with a range, not a single precise number.
5. Include search-call fees even when the provider currently discounts them.
6. Define a stop or review threshold for unexpected cost growth.

The most useful optimization target is cost per accepted or reviewable facet, not
cost per API request. Cheap calls that produce unusable evidence are not savings.

## 14. Safe Promotion Into `infrastructure.json`

Automatic publication should be implemented as a separate, single-writer command.
It should never run inside research worker threads.

Promotion procedure:

1. Read the canonical inventory and the append-only checkpoint.
2. Select the newest matching result for each facility and input fingerprint.
3. Promote only facets that pass schema, evidence, identity, and confidence rules.
4. Map each cited source into `datacenters/data/sources.json`, deduplicating by
   normalized URL and stable source ID.
5. Write canonical facet values plus the appropriate source ID arrays and
   verification date.
6. Preserve explicit uncertainty and distinguish reported facts from inference.
7. Reject conflicting newer canonical edits rather than overwriting them silently.
8. Write candidate JSON files to temporary paths on the same filesystem.
9. Run schema, generator, and map-data tests against the candidates.
10. After all tests pass, atomically replace `sources.json` first and then
    `infrastructure.json`. Publishing extra unused sources briefly is safe; publishing
    inventory source IDs before their source records is not.
11. Append a promotion event containing run ID, facility IDs, changed facets,
    source IDs, file hashes, and test result.

The coordinator should be idempotent: promoting the same checkpoint twice must not
duplicate sources or change already identical records.

`review` records may contain useful facets, but they should not be promoted wholesale.
A future promotion command may support facet-level acceptance after an explicit
review decision. `error` records must never be promoted automatically.

## 15. Map Publication

The map currently reads:

```text
/datacenters/data/infrastructure.json
```

Research checkpoint changes are visible in the Kimi inspector but do not appear on
the map until promoted into the canonical inventory. After promotion:

- Verify that the locally served JSON matches the filesystem copy.
- Load the map with browser caching disabled.
- Inspect representative data centers and power plants.
- Confirm new values, unknown states, and source links render correctly.
- Check mobile and desktop layouts.
- Treat browser verification as required; static JSON validation alone is not map
  acceptance.

## 16. Security And Data Handling

- Read `MOONSHOT_API_KEY` from the process environment or `.env.kimi`.
- Keep `.env.kimi` out of version control and restrict its file permissions.
- Bind control and dashboard APIs to loopback unless authentication is added.
- Do not expose raw checkpoints publicly without reviewing their contents.
- Treat web content as untrusted data, not instructions.
- Keep model output away from shell execution and filesystem paths.
- Validate URLs and structured data before use.

## 17. Recommended Commands

Inspect the queue without spending money:

```bash
python3 datacenters/research_inventory_with_kimi.py \
  --workers 4 --max-searches 5 --max-tier retry --dry-run
```

Run with a resumable checkpoint and REST controls:

```bash
python3 -X perf datacenters/research_inventory_with_kimi.py \
  --workers 4 \
  --max-workers 16 \
  --max-searches 5 \
  --max-tier retry \
  --control-host 127.0.0.1 \
  --control-port 8765 \
  --verbose
```

Pause, resize, resume, and stop:

```bash
curl -s -X POST http://127.0.0.1:8765/control \
  -H 'Content-Type: application/json' -d '{"paused":true}'

curl -s -X POST http://127.0.0.1:8765/control \
  -H 'Content-Type: application/json' -d '{"workers":4,"paused":false}'

curl -s -X POST http://127.0.0.1:8765/control \
  -H 'Content-Type: application/json' -d '{"stop":true}'
```

Run validation before changing pipeline code or promoting data:

```bash
python3 -m pytest -q
python3 -m py_compile \
  datacenters/research_inventory_with_kimi.py \
  datacenters/kimi_research_dashboard.py
```

Audit fetched evidence after collection. Direct source fetching does not incur
Kimi search charges; `--judge` uses K2.6 only on lexical candidates and does not
grant the judge a web-search tool:

```bash
python3 datacenters/audit_kimi_research.py \
  --judge \
  --workers 12 \
  --judge-workers 4
```

The audit produces two intentionally separate queues:

- `datacenters/research/kimi-repair-queue.json` contains evidence gaps that a
  targeted web-search pass may resolve.
- `datacenters/research/kimi-review-queue.json` contains absence claims, legal
  findings, and regulatory applicability questions that need a person or a
  reviewed rule rather than more generic searching.

Run only the targeted repair queue when another collection pass is justified:

```bash
python3 -X perf datacenters/research_inventory_with_kimi.py \
  --repair-queue datacenters/research/kimi-repair-queue.json \
  --workers 4 \
  --max-workers 16 \
  --max-searches 5 \
  --max-tier retry \
  --control-host 127.0.0.1 \
  --control-port 8765 \
  --verbose
```

Preview canonical changes first, then apply the same audited artifact. Promotion
is facet-level, rejects stale input fingerprints, requires a supporting URL
explicitly approved by the judge, persists generation overrides, records an
append-only transaction, and rolls all files back if canonical tests fail:

```bash
python3 datacenters/promote_kimi_research.py
python3 datacenters/promote_kimi_research.py --apply
```

After applying, verify both the canonical and locally served inventory:

```bash
python3 -m pytest -q tests/test_datacenters.py
curl -fsS http://127.0.0.1:8877/datacenters/data/infrastructure.json \
  | python3 -m json.tool >/dev/null
```

## 18. Definition Of Done

A research run is complete only when:

- Every targeted facility has a durable `ok`, `review`, or `error` checkpoint.
- No facility disappeared because of a worker or process failure.
- Costs, searches, retries, and model stages reconcile with the event log.
- Accepted facets have valid, facility-specific source support.
- Review and error populations have been sampled and categorized.
- Any promoted canonical data passes schema and map tests.
- The locally served map has been inspected after publication.
- Remaining uncertainty and coverage are reported explicitly.

High record count is not success by itself. Success is traceable evidence,
controlled cost, recoverable execution, and an inventory that does not overstate
what the sources establish.
