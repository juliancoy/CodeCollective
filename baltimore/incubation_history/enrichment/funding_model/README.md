# Typed fund and award evidence

Applied 2026-10-06. Migration `OrgPortal/org-worker/migrations/0075_funding_fact_model.sql` adds three flat tables without changing ledger balances or existing financial amounts.

## Entity and fact semantics

`funding_entities` distinguishes government, agency, statutory fund, program, appropriation account, and funding opportunity. An organization identity can represent a program without claiming it is separately incorporated. Administrator and legal entity are separate references. SEIF is classified as a statutory fund; the nine federal funding programs remain programs. No Treasury account symbols are inferred.

`funding_awards` reconciles agency award identifiers and supports recipient UEI and Assistance Listing Number. Three identifiers actually disclosed in the existing sources are populated: OMA-2120757, 2024-67023-42841, and 2024-38821-42091. UEIs and Assistance Listing Numbers remain null until sourced. Award identifiers are unique within the awarding agency.

`funding_facts` distinguishes reported award, program ceiling, appropriation, obligation, disbursement, balance, rescission, agency expenditure, and administration. Scope, measurement, fiscal year/basis, period, reporting date, agency, program, fund, appropriation account, and award are explicit flat fields. Unknowns remain null. Zero balances and signed obligation/disbursement corrections are supported. Rescission is a positive reduction magnitude, not a negative appropriation. Each fact retains its own source, evidence and review date.

Facts can link to an existing organizational support record; their amount and currency must match it. Linked amounts cannot be silently edited: corrections are new evidence with an explicit superseding link. Administrative facts cannot carry money. Program/fund/account/agency references must match their entity types. Reconciliation links cannot form cycles.

`included_in_fact_id` identifies overlapping components; `supersedes_fact_id` identifies replacement observations. `current_funding_facts` excludes voided and explicitly superseded facts. Cumulative observations require reconciliation: this view does not automatically infer that two records describe the same funding or sum cumulative snapshots. Agency-wide totals and recipient awards remain distinct scopes. These distinctions follow the separation of financial data elements described by [Treasury's Governmentwide Spending Data Model resources](https://tfx.treasury.gov/data-transparency).

## Initial classification

- 31 typed entities.
- 124 financial/administrative facts: 73 reported awards, two appropriations, two program ceilings, six agency expenditure aggregates, and 41 administrative records.
- Three source-disclosed award identifiers.
- No obligations, disbursements, Treasury account identifiers, UEIs, balances, or rescissions inferred from award announcements.

The initial records cover the Maryland and federal imports documented in adjacent directories. They are not an exhaustive inventory of government funds. Precise award/payment dates are not inferred from publication dates. SEIF FY2025 and TEDCO budget fiscal years use Maryland July–June periods; explicitly labeled CDC PHEP federal fiscal years use October–September periods. Other source years are left unclassified unless the fiscal-year basis is established.

## Access and validation

The existing public relationship feed exposes classification and funding references through `master_transaction_records`, preserving all original rows and columns. Public organization support reports add `fundingEntity` and paginated `fundingFacts` (use the existing `offset` query parameter for `fundingFacts.nextOffset`). These include standalone fund observations such as a zero balance. Existing monetary totals additionally group by financial fact type, measurement, and fiscal year, exclude classified non-flow context, and exclude superseded/included support facts.

Database views `funding_appropriations`, `funding_obligations`, `funding_disbursements`, `funding_reported_awards`, and `funding_balances` provide separate observations. These are database/API distinctions; new financial-basis selectors have not yet been added to the graph interface.

`scripts/prepare_funding_fact_backfill.py` prepares reviewable flat CSV and repeat-safe inserts from the existing import receipts. It changes classification, not source amounts or payment status. Database verification found no foreign-key failures and no change in the number of master transaction records. Schema tests cover classification, amount consistency, zero balances, negative corrections, superseding records, identifiers, entity types, and cycles. API tests cover typed fund reports and separation of award announcements from obligations and payments.
