# International power-plant source research task

You are working in `/home/julian/Documents/CodeCollective`. Follow `AGENTS.md`. This is a source-reconnaissance and adapter-design task, not permission to publish scraped records.

## Objective

Find high-quality, legally reusable, plant-level power-generation inventories outside the United States that can complement the separately labeled U.S. EIA, WRI Global Power Plant Database, and NACEI layers. Prioritize Canada and Mexico, then countries with authoritative national or grid-operator data.

## Source standard

Accept a candidate only when it provides or can reproducibly derive:

- individual generating facilities or units;
- latitude/longitude or a stable geospatial geometry;
- installed/nameplate capacity and units;
- technology or primary fuel;
- publisher, canonical URL, reference/update date, and license/terms;
- a stable download, documented API, or reproducible public query.

Rank sources:

1. national statistics office, energy ministry, regulator, ISO/TSO, or other government open-data publisher;
2. official intergovernmental dataset;
3. maintained academic/nonprofit dataset with public methodology and license;
4. commercial/open-web aggregation only as a lead, never as publishable truth.

Do not treat aggregate country/province tables, an image-only map, search snippets, or undocumented coordinates as a plant inventory. Prefer downloads and APIs over HTML scraping. Respect published terms, robots rules, and rate limits; do not bypass authentication, CAPTCHAs, or access controls.

## Work order

1. Audit Canada and Mexico first. Determine whether current official plant-level sources can supersede or corroborate WRI and the August 2017 NACEI comparison records.
2. Examine at least these promising jurisdictions: Brazil, United Kingdom, France, Germany, Spain, Australia, India, Japan, South Africa, and the European Union. Add others only when source quality meets the standard.
3. Download small samples into `datacenters/research/international/raw/<publisher>/`. Do not download bulk data over 250 MB without stopping and reporting it.
4. Record every candidate in `datacenters/research/international/source-manifest.json` with:
   `country_codes`, `publisher`, `dataset_title`, `canonical_url`, `download_or_api_url`, `license`, `reference_date`, `retrieved_date`, `facility_level`, `has_coordinates`, `has_capacity`, `has_fuel`, `record_count`, `format`, `update_cadence`, `quality_tier`, `limitations`, and `recommendation`.
5. For accepted sources, create adapter drafts under `datacenters/research/international/adapters/`. Adapters must write a temporary candidate GeoJSON, never `datacenters/data/*.json`.
6. Generate `datacenters/research/international/REPORT.md` containing source-by-source evidence, sample counts, schema mapping, freshness caveats, licensing, and a recommendation of `promote`, `comparison-layer`, `needs-review`, or `reject`.
7. Run adapters twice and prove byte-identical output. Validate unique IDs, coordinate bounds, numeric capacities, required provenance fields, and per-country counts.

## Required schema for candidate records

Keep source inventories separate. Never silently deduplicate or blend publishers. Each candidate record needs:

- `id` namespaced by publisher;
- `record_type: power_plant`;
- `inventory_source`, `country`, `country_code` (ISO 3166-1 alpha-3);
- `name`, `latitude`, `longitude`;
- `nameplate_capacity_mw`, `primary_technology`, normalized energy code;
- `source_name`, `source_url`, `source_year` or exact reference date;
- `location_tags` including country and `ISO3 <code>`;
- explicit license and coordinate provenance at dataset metadata level.

## Stop conditions

- Do not change the production map, generated production JSON, tests, deployment config, or source registry.
- Do not commit, push, or deploy.
- Do not promote a source solely because it has many records.
- Stop and report ambiguity when licensing forbids redistribution or plant coordinates appear security-restricted.

## Final response

Report the files created, countries researched, accepted/rejected source counts, exact validation commands and results, and the top three recommended production adapters. State all incomplete acceptance plainly.

## Assignment command

Reasoning level: `high`. This is enough for careful source/licensing/schema judgment; use `xhigh` only for a later difficult reconciliation pass.

```bash
codex exec -C /home/julian/Documents/CodeCollective -m gpt-5.4-mini -c 'model_reasoning_effort="high"' -s workspace-write - < datacenters/INTERNATIONAL_POWER_PLANT_RESEARCH_PLAN.md
```
