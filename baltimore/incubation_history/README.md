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
