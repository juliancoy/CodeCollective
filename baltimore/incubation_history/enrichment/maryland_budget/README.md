# Maryland public funding evidence

Applied 2026-10-06 to the live OrgPortal database. Flat organizational support rows use existing record kinds; no schema changes, ledger payments, memberships, or permissions are created.

## Coverage

- 56 FY2025 SEIF awards, USD 21,898,321.39: all Appendix C awards in Energy Efficiency Equity (39), Mechanical Insulation (2), Affordable Electrification Outreach (4), and Higher Education Green Energy Initiatives (11).
- Eight TEDCO total-budget context records: actual agency expenditures FY2020–FY2025 and appropriations FY2026–FY2027, as classified by Maryland State Archives.
- MEA's administrative relationship to SEIF.
- 43 additional organization identities. Existing UMB, UMBC, Loyola, and TEDCO identities reused. The existing UMB identity is named University of Maryland, Baltimore / UM Ventures; award recipient label remains the report's University of Maryland Baltimore.

Awards are `transfer`, status `reported`, amount label `reported award`: payment/settlement and exact award dates are unknown. Budget figures are `terms`, status `reported`; the default money graph excludes these agency aggregates and appropriations. Administration is `affiliation`. Neither proposed budgets nor fund balances become money transfers. All dates retain fiscal-year precision in descriptions/notes; `occurred_at` stays empty rather than inventing dates.

The SEIF fund is an administrative funding vehicle, not a separately incorporated grantor. Recipient award edges originate at MEA, with SEIF named as funding source. There is no duplicate SEIF-to-recipient edge.

Only Appendix C is imported; Appendix B repeats the same awards. The report prints the Energy Efficiency Equity organizational rows with program letter M; the actual program name is retained. Residential recipient lists, other SEIF programs, FY2024 and earlier award lists, and the complete enacted state operating/capital budgets remain outside this initial import. No exhaustive statewide coverage is claimed.

## Sources

- [MEA FY2025 SEIF report, Volume 2](https://energy.maryland.gov/Reports/FY25%20SEIF%20Volume%202_%20Appendices%20B%20and%20C%20-%20Appendix%20C-combined-compressed.pdf), organizational equity awards on PDF pages 119–120; remaining imported programs page 121.
- [MEA SEIF overview and report collection](https://energy.maryland.gov/Pages/Strategic-Energy-Investment-Fund-(SEIF)-.aspx).
- [Maryland State Archives TEDCO budget table](https://msa.maryland.gov/msa/mdmanual/25ind/html/71techb.html), code T50T01; actual versus appropriation labels retained.

`records.csv` preserves source page/row, fiscal year, record class and organization IDs. `organizations.csv` contains new identities. `apply.sql` is deterministic and uses conflict-safe inserts; rerunning creates no duplicate IDs. `preparation-summary.json` stores report SHA256. Live receipts and public verification are adjacent files.

Prepare using `scripts/prepare_maryland_budget_support.py --organizations <read-only Wrangler organizations JSON export>`. The script downloads the official PDF, requires `pdftotext`, validates expected program row counts and budget values, and writes reviewable SQL. Execute the reviewed SQL using the established administrative D1 credentials. It has no embedded credentials.
