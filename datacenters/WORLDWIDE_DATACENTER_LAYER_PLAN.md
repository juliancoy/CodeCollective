# Worldwide data-center layer implementation assignment

## Outcome

Implement and locally validate a source-labeled worldwide data-center layer in the existing data-centers map. The final result must be a working application layer, not merely a research report or a collection of candidate records.

Use the existing power-plant layers as the architectural pattern: keep datasets separated by source, expose geographic scope clearly, preserve provenance on every record, and render the same canonical records at every map scale.

This assignment is complete only when the generated dataset, checked-in generator, map controls, URL state, detail display, automated tests, and local browser acceptance all work together.

## Product and hierarchy requirements

Keep the curated Maryland data-center layer separate and most prominent. Replace the current OpenStreetMap U.S. data-center layer with one source-specific layer named:

`OpenStreetMap worldwide data centers`

Do not retain a second legacy OpenStreetMap U.S. layer. The worldwide layer must include a scope selector with these plain-language options:

- United States
- North America
- Worldwide

Default the scope to `United States` so the existing primary map experience remains focused, while worldwide coverage is directly discoverable.

Improve the data-center control hierarchy rather than adding another dense row of equal-weight controls:

1. Present a clear `Data centers` group before the power-plant group.
2. Show the curated Maryland card first and the OpenStreetMap worldwide card second.
3. In the worldwide card, make the layer name, source attribution, current scope, record count, and Render control the primary information.
4. Keep the scope selector adjacent to the Render control. A user should not need to open settings to discover worldwide mode.
5. Place search, visual styling, size, brightness, point-render mode, and zoom-range controls under the existing gear/settings interaction as secondary controls.
6. Keep Hover and Locate available as compact secondary actions with text or accessible labels. Locate must fit the selected scope.
7. Use a subdued source/vintage line under the layer name. Do not make provenance visually compete with the layer title, but do not hide it.
8. Use the status area for loading, errors, selected-scope record counts, and render diagnostics. Distinguish total matching records from rendered instance count if those values ever differ.
9. On narrow mobile screens, preserve this reading order: title, source, status/count, scope, Render, secondary actions. Do not allow horizontal overflow.
10. Preserve full keyboard operation, visible focus, associated labels, appropriate ARIA state, and touch targets suitable for mobile.

Use existing visual tokens and control components. Do not redesign unrelated layers.

## Source and publication rules

OpenStreetMap is the baseline worldwide source because its source objects, coordinates, and redistribution terms can be documented. Include all qualifying OpenStreetMap elements available from the selected reproducible extract or query, subject to its license and attribution requirements.

Recognize both British and American tag spellings, including relevant combinations such as:

- `data_center`
- `data_centre`
- qualifying `building`, `industrial`, and `telecom` tags

Document the exact inclusion and exclusion rules in the generator. Do not treat generic offices, telephone exchanges, warehouses, hosting-company mailing addresses, or city-level directory listings as physical data centers without an explicit qualifying source tag.

Do not bulk-copy PeeringDB, Cloudscene, Data Center Map, Baxtel, or another directory unless its current terms explicitly authorize redistribution. Public visibility alone does not establish publication rights.

If you identify a high-quality national government or openly licensed country dataset, do not merge its records into the OpenStreetMap layer. Record it in the source report as a candidate for its own future source-labeled layer. This run should remain simple and finish the OpenStreetMap worldwide layer successfully.

## Reproducible data pipeline

Create or adapt a checked-in generator whose clear purpose is to generate the worldwide OpenStreetMap data-center dataset. Name the generated asset consistently, for example:

`datacenters/data/data-centers-openstreetmap-world.json`

The generator must:

- Fetch or consume a documented, reproducible OpenStreetMap snapshot or extract.
- Record snapshot date, retrieval date, source URL, license, attribution, and generator version or command.
- Process nodes, ways, and relations. Use exact node coordinates and a documented representative coordinate for ways and relations.
- Preserve the OpenStreetMap element type and ID so every feature has a stable source identity and inspectable source URL.
- Normalize names, operator, address fields, lifecycle hints, facility/campus hints, and useful source tags without inventing missing values.
- Add standard geolocation fields: latitude, longitude, country code, country name, first-level administrative region when available, city/locality when available, and a structured `location_tags` collection.
- Assign ISO country metadata using an openly licensed, documented boundary dataset. Make boundary-version and edge-case behavior reproducible.
- Retain source-specific records. Deduplicate only repeated ingestion of the exact same OpenStreetMap element identity.
- Keep campus and contained-building records distinct and expose their source tags so later review can relate them.
- Produce deterministic ordering and stable IDs.
- Validate numeric coordinates and legal latitude/longitude bounds.
- Fail clearly rather than silently publishing a partial download.

Do not prune records from the generated source file for level of detail. Filtering and rendering decisions belong in the application.

## Application integration

Replace the existing layer ID and data source for `openstreetmap-us-data-centers` with a straightforward worldwide equivalent such as `openstreetmap-world-data-centers`. Do not add compatibility aliases for the old ID.

Integrate the layer into the existing layer inventory, ordering, search, hover/inspection, settings, color controls, URL serialization, and map fitting behavior.

The layer must:

- Filter by the three visible scope options without reloading the page.
- Persist the scope in the share URL using one compact, documented query parameter or the existing canonical state mechanism.
- Restore the same scope, enabled state, ordering, and settings after a page reload.
- Show the exact source name and OpenStreetMap object link in feature details.
- Show country, region, locality, coordinates, operator, element identity, tags, snapshot date, and license where available.
- Participate in layer search and hover without obscuring the curated Maryland layer.
- Fit the selected scope when Locate is used.
- Render every matching record in individual-points mode at every zoom. Simple point/instance resizing must not disappear merely because the map is zoomed out.
- Keep any adaptive LOD optional and explicitly disableable in settings. If LOD exists, show source `recordCount` separately from rendered `instanceCount`.
- Prefer the existing efficient point or GPU-instanced rendering path when it materially improves responsiveness, but do not create a second rendering architecture solely for this layer.

At world extent, points may become visually smaller or be density-styled, but the user-selected size control must still have a visible effect and records must not silently vanish.

## Research record

Create a concise source and coverage report under:

`datacenters/research/worldwide-datacenters/`

Include:

- The exact OpenStreetMap query or extract workflow.
- Inclusion and exclusion rules.
- Snapshot and boundary-source versions.
- Record counts by country and by element type.
- Counts lacking country, region, locality, name, or operator.
- Any failed regions, download gaps, or unresolved boundary cases.
- Openly licensed national sources found during research, each labeled as a separate future-layer candidate with license evidence.
- Rejected commercial or unclear-license sources and the rejection reason.

Do not claim complete knowledge of every physical data center worldwide. State precisely that the layer contains all records qualifying under the documented source snapshot and rules.

## Evidence-backed power enhancement

Implement the base worldwide layer without fabricating missing power data. Prepare the separate review-gated workflow in `datacenters/WORLDWIDE_DATACENTER_ENRICHMENT_PLAN.md` so Kimi can research facility-level megawatts, lifecycle, and energy evidence after stable source identities exist.

The worldwide layer must be able to consume that workflow's sparse, source-specific enrichment overlay, but the layer implementation must not depend on completing an unbounded worldwide paid-research run. Only reviewed and promoted values may affect marker sizing or appear as reported facts.

## Tests and browser acceptance

Add focused automated coverage for the generator, schema, geographic scope filtering, deterministic IDs/order, URL state, and layer registration. Extend the Selenium smoke runner with a dedicated worldwide-data-centers mode.

Before finishing, run the relevant repository checks, including at minimum:

- Generator/schema tests and JSON parsing.
- `python -m py_compile` for changed Python.
- `node --check` for changed JavaScript.
- `git diff --check`.
- `PYTHONPATH=. pytest -q` or the narrowest valid repository test command followed by the full suite if practical.

Exercise the page locally in a real browser at desktop and approximately 390 x 844 mobile size. Verify with evidence:

- Maryland remains the first and distinct curated data-center layer.
- The source is visibly named `OpenStreetMap worldwide data centers`.
- United States, North America, and Worldwide scopes produce plausible, different counts and extents.
- Render and size adjustments visibly affect individual points at a world-level zoom.
- The settings panel contains secondary styling controls and LOD can be disabled if present.
- Locate fits the selected scope.
- A shared URL reload restores scope and layer state.
- Feature inspection exposes exact source identity and geolocation fields.
- The status area reports total records separately from rendered instances when applicable.
- The card has no mobile overflow and remains keyboard accessible.
- The browser console has no new errors.

Use screenshots, DOM assertions, and application diagnostics as appropriate. Do not accept a test that checks only file presence or JavaScript variables.

## Working constraints and final report

Work only in the current branch. Preserve unrelated changes in the working tree. Keep generated production data when it is part of the maintained application pipeline.

Do not commit, push, or deploy. Leave a reviewable local implementation.

Finish with:

1. Files changed and generated.
2. Source snapshot, license, and exact record counts.
3. Counts by geographic scope and country.
4. UI hierarchy and URL-state behavior implemented.
5. Tests and browser checks run, with results.
6. Any remaining data or acceptance gap stated plainly.

Do not declare success unless the worldwide data-center layer is integrated and demonstrably working in the local map.
