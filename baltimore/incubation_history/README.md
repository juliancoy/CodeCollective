# Pitch and incubation history

This is a generated research queue, not OrgPortal's organization registry.
The report supplies provenance; its companion `event_history.json` supplies
records. All 16,235 records were scanned. The result contains 99 relevant
records and three excluded matches. These are event records, not 99 distinct
competitions: repeated listings, program deadlines, workshops, and showcases
are retained with their original index and commit provenance.

Regenerate from the CodeCollective checkout:

```sh
python scripts/prepare_incubation_history.py
python scripts/test_incubation_history.py
```

The flat tables and CSVs are:

| Table | Purpose |
| --- | --- |
| events | Event evidence, category, date, organizer label, source, archive commits, research status |
| organizations | 26 explicitly named organizations; research IDs are not portal IDs |
| event_organizations | One named participant, accelerator, or supporter per row with evidence |
| support_candidates | Eight named accelerator-to-company links; no nested organizations |

`research.sqlite` is a disposable local artifact; the CSVs carry the same rows.
`summary.json` records counts and hashes of both source files. Rebuilding does
not preserve edits to generated files. Keep reviewed portal ID mappings in a
separate CSV.

## Findings

There are 23 competition records, 32 demo/showcase records, 13 incubation or
acceleration program records, 28 pitch practice/networking records, two matches
found in descriptions, and one accelerator program workshop. Exclusions cover
MLB Pitch, Hit, and Run; Pitch & Pints (rugby); and climate-policy accelerators.

Programs include Techstars AI Health Baltimore, Conscious Venture Lab,
Baltipreneurs, Cyber Howard, HoCo Higher, HBCUFI, Foundervine, SHRM Labs,
Summer Launch Incubator, and CoMotion Labs. Competition/showcase leads include
ChesaPitch, Morgan State, Bowie State Bulldog Pitch, UBalt Rise to the Challenge,
Cangialosi, Agora, AWS AI, Greater Baltimore Urban League, Maryland Student
Venture Showcase, Maryland NEW VENTURE, MEIA, and the BDC incubator graduation.
These names are leads from the archive, not validated legal identities.

The Spring 2025 Techstars description explicitly names AidRx, Behaivior,
Compose Health, Embryoxite, Galen Health, Opal, Sloop, and Valio. It identifies
Johns Hopkins University and CareFirst BlueCross BlueShield as partners and
Brex as a corporate supporter. The latter are event/program supporters; the
archive does not establish direct support from each to each cohort company.

Pitch Labs descriptions name Ginger Cybersecurity, IPRights4All, ValiCor US,
ACURE, N0S.AI, MiFido, Sentype, Countacus, Nova Hospitality, Caldarium, and Open
Judgement Engineering as presenters. Participation does not establish incubation
or sponsorship, so they have no incubation support candidates.

The October 7, 2026 BDC graduation listing names BDC, LISC, and Verizon Small
Business Digital Ready, but does not name its 11 participants or three finalists.
They remain recipient research tasks. Provider labels and domains are retained
as evidence; Eventbrite, Meetup, and Luma are never assumed to be sponsors.

## Register and link through OrgPortal

OrgPortal's upstream `0057_organization_support.sql` already supplies flat
`organization_support_records`: one supporter ID and recipient ID per row,
foreign keys to the existing registry, typed support, source evidence, status,
and directional indexes. The support view omits voided records and contextual
terms/portfolio/affiliation records. No parent pointer, embedded company list,
new membership, ownership claim, or identity credential is needed.

Resolve each research identity against the existing OrgPortal registry first.
If absent, use `preview_organization_creation` and `apply_organization_creation`
with the existing authorized account. Creating an organization establishes an
owner; do not claim or create externally owned companies merely to import a
research mention. Confirm the organization's actual identity, city, and URL.
The archive's location strings and organizer feed URLs are research evidence,
not automatically canonical registration fields.

Keep a reviewed `identities.csv` with columns `research_id,portal_organization_id`.
Blank portal IDs remain unresolved. Prepare relationship preview requests:

```sh
python scripts/prepare_incubation_portal_queue.py \
  --identities /path/to/identities.csv \
  --output /path/to/support-previews.jsonl
```

The queue contains `preview_organization_support` tool arguments validated by
the upstream support schema. Its occurrence date is the showcase date, not an
asserted incubation start date. Each candidate has `reported` status. The queue
script does not authenticate, invoke MCP, or mutate the registry.

Use the existing browser-bound portal/MCP login and organization management
permissions to obtain previews, review the exact evidence and matched IDs, then
use `apply_organization_support` with the matching one-use `previewId` and
`confirm: true`. Check existing support records before applying to avoid adding
duplicate historical reports. Scopes never substitute for live permissions.

No production migration, organization creation, support write, or deployment
was performed by these research scripts. The upstream support functionality was
being added in the shared workspace during this task; its presence locally does
not establish production availability. Shared release work belongs to OrgPortal
and the CodeCollective deployment flow, not MedTech.

## Live event import — October 4, 2026

All 99 reviewed event records are now first-class OrgPortal events associated
with LifeTech, using the same event records and features as MedTech. The import
created 93 records and reused six existing records. Original tags were preserved,
with `LifeTech`, `Entrepreneurship`, `life-tech-event-history`, and the applicable
pitch/showcase/program classification added. Original organizer, source, and
date information remain available. No organization ownerships or memberships
were created. LifeTech's collection contains 100 events including MedTech in
the Hut.

Every imported event was verified in the live collection with its expected tags
and a successful event-detail API response. The LifeTech event list and an
imported detail page also returned HTTP 200. An upstream URL lookup fix preserves
stored slugs ending in hyphens or containing long collision suffixes; 37 relevant
Worker tests and type checking passed before release.

- Live collection: https://lifetech.fyi/org-events
- Successful deployment/import run: https://github.com/juliancoy/CodeCollective/actions/runs/37221245937
- OrgPortal release commit: `ca750df3a7aeabc85af2b696b7cf1a4279fbfa09`
- Org Worker version: `b84e2932-724d-494f-b47d-bff55ebcd0a6`
- Public import receipt: `live-receipt/lifetech-import-receipt.json`
- Reviewed ingest payload: `lifetech-import.json`
- Original archive provenance: `lifetech-import.manifest.json`

The dedicated `.github/workflows/import-lifetech-history.yml` uses the existing
authorized calendar ingest interface. Backend release and credential synchronization
are explicit dispatch options; ordinary reruns reuse the deployed backend and
preserve existing event metadata. The first import repaired the documented
GitHub Actions/Worker ingestion credential mismatch. Credentials are not included
in any repository artifact. The normal recurring calendar workflow is unchanged.

## Web research preparation (2026-10-04)

The `enrichment/` directory audits all 99 live records. `research_tasks.csv`
contains targeted search queries for remaining fields, participants and supporting
organizations. `sources.csv` records the 91 original URLs checked;
`event_field_candidates.csv` contains 214 machine-extracted suggestions. These
are candidates, not approved replacements: a source may describe a different
edition, and date conflicts require review. Thirty-three original URLs could not
be fetched. Empty values remain unknown rather than receiving invented defaults.

Additional primary-source research is recorded in `verified_sources.csv`.
`entities.csv`, `cohort_relationship_candidates.csv`,
`verified_event_participants.csv`, `published_awards.csv`, and
`organization_facts.csv` are flat tables joined by IDs. They contain 56 cohort
relationships across seven cohorts, 20 published awards, and four program
sponsors. `event_research_coverage.csv` covers every imported record; ten records
have primary participant or award evidence, and the others retain their search
queue. Primary evidence does not resolve every field of those ten records.
`conflicts.csv` preserves discrepancies and a possible duplicate NEW VENTURE
event. The local `verified_research.sqlite` is a convenience copy of these CSVs.

Reproduce the source-page audit (network access required):

```sh
python scripts/research_lifetech_event_gaps.py --help
```

Regenerate the curated evidence tables and validate their references:

```sh
python scripts/prepare_lifetech_verified_research.py
python -m unittest discover -s scripts -p test_lifetech_verified_research.py
```

The curated generator embeds the reviewed factual source selections so output
can be reproduced without a network call; it does not revalidate changing pages.
All names are research identities, not claims of incorporation or portal IDs.
Before applying, match each identity to an existing organization or review its
creation, then use OrgPortal's preview/apply receipts and existing support queue.
The `program_participation` research label requires an explicitly reviewed mapping
to a supported portal relationship; it is not an OrgPortal enum. Prize awards do
not prove incubation or settled payments. Program sponsorship does not prove a
direct financial transfer to each cohort member. Unknown allocations in a shared
prize pool remain blank. No enrichment writes have been made to production.

## Authorized live research application (2026-10-04)

The verified account behind MedTech's `.env.pidp` authenticated successfully but
was initially absent from OrgPortal's administrator allowlist. The verified
account ID was added to the existing `ADMIN_USER_IDS` configuration, retained in
CodeCollective's canonical GitHub release variable and local release environment.
PIdP credentials, identity flags, memberships and organization ownership were not
modified. `admin-configuration-receipt.json` and `permission-check-receipt.json`
record the configuration repair and successful management checks without tokens.

The shared portal now supports operator registration of unclaimed public-evidence
organizations and permission-checked event enrichment using existing expiring,
actor-bound preview/apply receipts. Changes live upstream in
[OrgPortal PR 4](https://github.com/juliancoy/OrgPortal/pull/4).
The historical slug fix is tracked in
[OrgPortal PR 5](https://github.com/juliancoy/OrgPortal/pull/5).
The backend was released through CodeCollective's org-only deployment path with
existing variables retained and without database migrations or frontend releases.

`enrichment/reviewed-registration-plan.jsonl` contains the reviewed registrations;
`enrichment/applied-portal-identities.csv` maps research IDs to portal IDs.
`enrichment/live-enrichment-receipt.jsonl` preserves each preview and apply result.
The final current counts and verification are in
`enrichment/live-enrichment-summary.json` and
`enrichment/live-enrichment-verification.json`.
Earlier preparation summaries and unresolved identity queues are historical
snapshots, superseded by these application receipts.

The live support records distinguish acceleration from educational/mentoring
services. Maryland NEW VENTURE participation maps to `services`, with the reason
in each record's notes. Award facts are added to the applicable events' public
metadata, with source links and a clear statement that payment is unverified;
they are not inserted as transfers or incubation relationships. Shared prize
allocations and unknown amounts remain blank. Unavailable sources and research
conflicts remain pending.

The resumable application script uses the existing portal interfaces:

```sh
python scripts/apply_lifetech_research.py --env-file ../bmoremedtech/.env.pidp
python scripts/apply_lifetech_research.py --env-file ../bmoremedtech/.env.pidp --apply
```

The first command prepares registrations without production writes. The second
inspects and applies actor-bound previews, honors portal rate limits, checks for
already-recorded evidence, and verifies each change. Do not run with a different
identity or bypass the portal's management checks. Credentials are read in memory
and excluded from receipts. Original cohort evidence CSVs are immutable research
inputs; the separate identity mapping and receipts describe production state.
