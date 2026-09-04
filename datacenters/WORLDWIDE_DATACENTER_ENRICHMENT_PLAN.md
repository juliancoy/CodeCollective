# Worldwide data-center evidence enrichment assignment

## Outcome

Build a review-gated data enhancement pipeline for the OpenStreetMap worldwide data-center layer. Reuse the existing Kimi research machinery where it is genuinely generic, but keep worldwide research, audits, repair queues, overrides, and generated output separate from Maryland's canonical `infrastructure.json` pipeline.

The enhancement must produce source-backed power and lifecycle fields that the worldwide layer can render with the same visual semantics as the curated Maryland data-center layer. It must never invent megawatts merely to make icons larger.

Do not begin with an unbounded paid run. Complete the implementation and dry run, then run and audit a small diverse pilot before proposing a larger batch.

## Existing machinery to reuse

Reuse or extract shared components from:

- `datacenters/research_inventory_with_kimi.py`: Moonshot/Kimi client, web-search tool loop, retry/backoff, checkpointing, fingerprints, tiered models, cost metrics, concurrency, and loopback control API.
- `datacenters/kimi_research_quality.py`: source fetching, content hashing, text extraction, URL normalization, identity matching, excerpts, and atomic JSON/JSONL writes.
- `datacenters/audit_kimi_research.py`: latest-result selection, evidence fetching, repair/review queues, and optional claim-entailment judge.
- `datacenters/promote_kimi_research.py`: stale-input detection, review-gated promotion, transactional writes, rollback, history, and post-promotion tests.

Do not copy these scripts wholesale into a parallel implementation. Add a small named research-profile abstraction or extract shared functions so the existing Maryland workflow remains simple and independently testable.

## Strict separation from Maryland

Use dedicated worldwide paths, for example:

- Research input: `datacenters/research/worldwide-datacenters/enrichment-input.json`
- Checkpoint: `datacenters/research/worldwide-datacenters/kimi-power-research.jsonl`
- Events: `datacenters/research/worldwide-datacenters/kimi-power-events.jsonl`
- Evidence audit: `datacenters/research/worldwide-datacenters/kimi-power-audit.jsonl`
- Repair queue: `datacenters/research/worldwide-datacenters/kimi-power-repair-queue.json`
- Human-review queue: `datacenters/research/worldwide-datacenters/kimi-power-review-queue.json`
- Published overlay: `datacenters/data/data-centers-openstreetmap-world-enrichment.json`
- Promotion history: `datacenters/history/worldwide-datacenter-enrichment-history.jsonl`

Do not write worldwide records or worldwide evidence sources into:

- `datacenters/data/infrastructure.json`
- `datacenters/data/research-overrides.json`
- Maryland's `datacenters/data/sources.json`, unless a later deliberate migration creates a shared source registry.

The worldwide base inventory remains OpenStreetMap-derived. The enrichment file is a sparse overlay joined by stable source identity:

`source_id + osm_type + osm_id`

Display source labels must continue to distinguish `OpenStreetMap worldwide data centers` from `Maryland curated data centers`.

## Research-input adapter

Add a deterministic adapter that accepts the generated worldwide GeoJSON `FeatureCollection` and emits the JSON-array shape expected by the research engine.

For each target, preserve at minimum:

- Stable research ID, such as `osm-way-12345`.
- `record_type: data_center`.
- OSM type, OSM ID, OSM URL, and snapshot date.
- Facility name, aliases, operator, owner, campus, and website when present.
- Street address, locality, first-level region, postal code, country name, ISO country code, latitude, and longitude.
- Facility tags and location tags.
- Any already published power or lifecycle fields and their provenance.

Do not send unnamed building footprints with no operator, address, website, campus, or other useful identity signal into paid research. Put them in a deferred queue with an explicit reason. Prioritize targets deterministically:

1. Named facility plus operator and official website.
2. Named/operator facility with a complete address.
3. Named campus or facility with locality and stable OSM identity.
4. Weakly identified records, deferred until a later identity-resolution pass.

Detect likely campus/building relationships, but do not merge them automatically. Research must state whether a power figure applies to a building, facility, campus, availability zone, regional portfolio, or company fleet.

## Worldwide research profile

Add a named profile such as:

`worldwide-datacenter-power`

It must not use the existing Maryland-specific system prompt. Its prompt should instruct Kimi to search in the facility's country and relevant local language when useful, while returning English-normalized structured data. Prefer sources in this order:

1. National, regional, and local government permits, planning decisions, energy filings, and environmental records.
2. Utility, grid-operator, regulator, and market-operator records.
3. Official facility operator specifications, sustainability reports, planning submissions, and investor filings.
4. Audited engineering, lender, or property documents tied to the exact facility.
5. High-quality reporting only as a lead or as clearly labeled secondary evidence.

Directories and search snippets are leads, not sufficient evidence. Never transfer a fleet, market, region, campus, or announced investment figure to an individual facility unless the source explicitly establishes that scope.

Search alternate spellings, local-language facility names, operator subsidiaries, campus names, addresses, and the exact OSM identity context. Require at least two distinct searches for a pilot record and at least one attempt aimed at a primary or official source.

## Structured enhancement schema

Research one compound facet named `power_profile` so related figures are evaluated together and contradictory scopes are visible. Each result must retain the existing outer evidence contract (`value`, `confidence`, `basis`, `sources`) and add a `fields` object:

```json
{
  "value": "Concise, scope-aware facility power summary",
  "confidence": "high | medium | low | insufficient",
  "basis": "What the cited evidence establishes and its limits",
  "fields": {
    "reported_grid_demand_mw": null,
    "reported_power_capacity_mw": null,
    "projected_power_demand_mw": null,
    "estimated_power_draw_mw": null,
    "estimated_power_draw_method": null,
    "on_site_generation_capacity_mw": null,
    "energy_source_codes": [],
    "lifecycle_status": null,
    "value_scope": "building | facility | campus | availability_zone | portfolio | unknown",
    "as_of_date": null
  },
  "field_evidence": {
    "reported_power_capacity_mw": ["https://source.example/document"]
  },
  "sources": []
}
```

Validation requirements:

- MW values are JSON numbers greater than or equal to zero, or `null`; never strings such as `"50 MW"`.
- `reported_grid_demand_mw` is operating grid demand explicitly reported for the facility.
- `reported_power_capacity_mw` is a published power envelope or capacity, not measured consumption.
- `projected_power_demand_mw` applies only to proposed, approved, or under-construction facilities.
- `estimated_power_draw_mw` is allowed only when a documented method and confidence are present. Preserve the inputs used by the calculation.
- Backup-generator nameplate capacity must not be treated as facility power demand.
- IT load, critical load, utility service, substation capacity, grid reservation, and total campus capacity are not interchangeable. Preserve the publisher's term and map it only when the mapping is defensible.
- Values expressed in kW or GW must retain their original value/unit in evidence metadata and be converted deterministically to MW.
- A number without facility identity, unit, and scope remains unpublishable.
- Each non-null field must list at least one supporting source URL in `field_evidence`.
- Conflicting values remain visible to review; do not silently choose or average them.

## International evidence audit

The current auditor's primary-source classification is oriented toward U.S. `.gov`, `.mil`, and court domains. Do not weaken that rule globally by trusting a model-supplied `source_type` string.

Add an explicit, checked-in authority registry for accepted government, regulator, grid-operator, utility, and official operator domains. Each registry entry must include country code, authority class, domain, publisher, and justification. Unknown domains remain non-primary until reviewed.

Extend evidence auditing for `power_profile` to require:

- Reachable content and a captured content hash.
- Facility identity match.
- Power/capacity terminology match.
- The claimed number, compatible unit, and claimed scope in the retrieved evidence excerpt.
- Every non-null structured field to be supported by its declared source URLs.
- A supported Kimi judge verdict before automatic promotion.
- Human review for estimates, conflicting values, scope ambiguity, negative/absence claims, and operator-only evidence without a corroborating official record.

An official operator specification may be publishable after human review, but it must be labeled `operator-reported`. Do not mislabel it as government-verified.

## Promotion contract

Create a worldwide-specific promoter that reads only promotion-ready worldwide audits and writes the sparse overlay. Default behavior is dry run; require `--apply` for mutation.

For every promoted field, store:

- Value and semantic field name.
- Value scope.
- Confidence and whether it is reported, projected, or estimated.
- Basis and as-of date.
- Source records with title, publisher, document date, retrieval date, URL, source class, and content hash.
- Research run ID, pipeline ID, input fingerprint, and audit/judge result.

Reject promotion when:

- The base OSM identity or relevant identity context changed after research.
- The country, facility, campus, or address match is ambiguous.
- A value is not numeric or lacks a unit/scope.
- Evidence URLs or content hashes are missing.
- The record would overwrite a newer or more authoritative reviewed value without an explicit conflict decision.

Write transaction history before and after applying changes, validate the candidate overlay, regenerate the map asset through its checked-in generator, run tests, and roll back atomically on failure.

## Map integration semantics

The worldwide layer may consume the overlay only after promotion. It must use the same field meanings as Maryland:

- Size priority for unbuilt facilities: `projected_power_demand_mw`.
- Size priority for operating facilities: `reported_grid_demand_mw`, then a clearly labeled `reported_power_capacity_mw` proxy, then a documented estimate.
- Missing values use the Maryland missing-value size; absence is not zero.
- Inspector text explicitly labels reported demand, published capacity envelope, projected demand, and estimate.
- Source and value scope remain visible in the inspector.

Do not allow enrichment to alter OSM geometry or source identity. Location corrections belong in the base-source generator or upstream OpenStreetMap, not in the power overlay.

## Cost-controlled execution

The adapter and runner must print before API execution:

- Total eligible and deferred records.
- Counts by country and priority tier.
- Already-completed and pending fingerprints.
- Minimum search calls.
- Estimated lower-bound search and token cost using the checked-in pricing snapshot.

Provide country, ID, priority, and `--limit` filters. Preserve append-only checkpoints so interrupted runs resume without paying twice for unchanged targets.

Run this progression:

1. Dry run over the current source inventory.
2. Five-record pilot spanning at least three countries, multiple operators, and both facility/campus records.
3. Fetch and audit all pilot citations.
4. Run the entailment judge on eligible pilot facets.
5. Dry-run promotion and inspect the exact overlay diff.
6. Apply only the reviewed pilot if every validation passes.
7. Report evidence yield and actual cost before proposing the next batch.

Do not launch the full worldwide queue merely because the pilot completed.

## Suggested commands

The implementation may choose precise script names, but it must support an equivalent workflow:

```bash
python datacenters/prepare_worldwide_datacenter_enrichment.py \
  --input datacenters/data/data-centers-openstreetmap-world.json \
  --output datacenters/research/worldwide-datacenters/enrichment-input.json \
  --report datacenters/research/worldwide-datacenters/enrichment-input-report.json

python datacenters/research_inventory_with_kimi.py \
  --profile worldwide-datacenter-power \
  --input datacenters/research/worldwide-datacenters/enrichment-input.json \
  --checkpoint datacenters/research/worldwide-datacenters/kimi-power-research.jsonl \
  --events datacenters/research/worldwide-datacenters/kimi-power-events.jsonl \
  --limit 5 \
  --workers 2 \
  --dry-run

python datacenters/audit_kimi_research.py \
  --profile worldwide-datacenter-power \
  --inventory datacenters/research/worldwide-datacenters/enrichment-input.json \
  --checkpoint datacenters/research/worldwide-datacenters/kimi-power-research.jsonl \
  --output datacenters/research/worldwide-datacenters/kimi-power-audit.jsonl \
  --repair-queue datacenters/research/worldwide-datacenters/kimi-power-repair-queue.json \
  --review-queue datacenters/research/worldwide-datacenters/kimi-power-review-queue.json \
  --judge

python datacenters/promote_worldwide_datacenter_enrichment.py \
  --audit datacenters/research/worldwide-datacenters/kimi-power-audit.jsonl \
  --base datacenters/data/data-centers-openstreetmap-world.json \
  --overlay datacenters/data/data-centers-openstreetmap-world-enrichment.json
```

The last command must remain a dry run unless `--apply` is explicitly supplied.

## Tests and acceptance

Add focused tests for:

- GeoJSON-to-research adapter determinism and identity preservation.
- Priority/deferred rules.
- Profile-specific prompt and exact structured schema.
- Numeric/unit/scope validation, including kW and GW conversion.
- Rejection of backup capacity as demand.
- Rejection of fleet/portfolio values assigned to a facility.
- International authority registry classification.
- Evidence excerpts containing identity, number, unit, and scope.
- Fingerprint resume and stale-result rejection.
- Source-specific overlay promotion, history, rollback, and idempotence.
- Maryland Kimi workflow remaining unchanged.

Run at minimum:

```bash
python -m py_compile datacenters/*.py
PYTHONPATH=. pytest -q tests/test_kimi_inventory_research.py tests/test_kimi_research_quality.py
PYTHONPATH=. pytest -q
git diff --check
```

For the pilot, additionally validate the generated overlay against the base data, load the local map, inspect every promoted pilot record, and confirm its size and inspector labels match Maryland semantics.

## Final report

Report:

1. Shared Kimi components reused or extracted.
2. Files created or changed.
3. Eligible/deferred counts by country and priority.
4. Pilot facility IDs and why they were selected.
5. Actual search count, token usage, and estimated cost.
6. Evidence states and rejection reasons by field.
7. Exact promoted fields, values, scopes, and sources.
8. Tests and browser checks run.
9. Remaining ambiguity and whether a larger run is justified.

Do not commit, push, deploy, or run an unbounded paid job. Leave implementation and pilot results reviewable in the current working tree.
