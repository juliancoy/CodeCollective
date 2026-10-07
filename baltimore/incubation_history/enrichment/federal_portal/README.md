# Federal government registration

Applied to live OrgPortal on 2026-10-06 using the existing administrative D1 workflow.

- United States Federal Government parent identity.
- 17 federal agencies, reusing the existing NIH identity.
- Nine funding-program identities: SSBCI, SBOP, FAST, STEP, PHEP, PHIG, CERSI, SUPER, and NSF Quantum Leap Challenge Institutes.
- Existing 32 sourced federal research records registered as organizational support.
- 27 new nonfinancial links: nine government-to-department/independent-agency links, nine program administration links, and nine program participation links. Existing department-to-subagency links remain in the original 32 records.
- 33 new organization IDs, including documented recipient institutions. Existing TEDCO, NIH, and University of Maryland College Park identities reused.

Organizations and relationships are flat rows, with no nested agency trees. Program identities are administrative research entities, not claims of separate incorporation. Federal jurisdiction and funding-program tags identify their roles. No accounts, membership, permissions, or ledger payments are created.

Imported research rows retain their published award amounts, dates, sources, notes, reported status, and distinctions between awards and program ceilings. No new appropriation or government-wide balance is inferred. Program administration and participation links have no monetary amounts. Original agency-to-recipient awards are not repeated as program-to-recipient money flows.

Source research is the existing deployed `OrgPortal/web/public/ecosystem-data/ecosystem-relationships.json`, with its source URLs and review notes preserved. Additional root links cite the [USAGov agency directory](https://www.usa.gov/agency-index). Program links cite primary agency or recipient sources including [Treasury SSBCI](https://home.treasury.gov/policy-issues/small-business-programs/state-small-business-credit-initiative-ssbci), [Treasury Maryland SBOP award](https://home.treasury.gov/news/press-releases/jy2566), [SBA grants](https://www.sba.gov/loans/additional-funding-opportunities/grants/), [CDC Maryland funding](https://www.cdc.gov/readiness/php/data-research/maryland-funding.html), and [FDA CERSI](https://www.fda.gov/science-research/advancing-regulatory-science/centers-excellence-regulatory-science-and-innovation-cersis). This registers existing research coverage; it does not claim a comprehensive federal budget import.

Existing 32 static research edges are registered with the established `bmoremedtech:` import prefix. The graph merger already excludes that prefix, so the static evidence remains displayed once while OrgPortal gains first-class support history. New administrative links use `federal-portal:` and appear from the live public feed. The USA parent has nine direct links and satisfies the default sparse-node visibility threshold. Money-only mode excludes administrative relationships; federal funding award edges remain available.

`scripts/prepare_federal_portal_import.py --organizations <read-only Wrangler organizations export>` writes reviewable CSV and conflict-safe SQL. Before applying, SQL was run twice against an in-memory SQLite schema with foreign keys enabled. After applying, all 59 records were verified in the live public feed; the current graph merge was checked for government classification, connectivity, duplicate research edges, and exclusion of administration from money-only mode. See `live-public-verification.json` and the administrative apply receipt.
