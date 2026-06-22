# TODO

## Large-Scale Governance Readiness

The portal is more representative than a simple prototype, but it is not yet a complete system for governing a large body of people. Treat the current governance and finance workflows as an early operational foundation that still needs formal rules, stronger server-side enforcement, auditability, and operational hardening before it is used for consequential decisions.

## Governance Gaps

- Define the actual bylaws, rules of order, notice requirements, quorum rules, eligibility rules, amendment rules, appeal rules, and committee/meeting procedures the software must enforce.
- Build a rules engine or explicit policy layer for motions, amendments, seconds, discussion windows, voting windows, tabling, withdrawal, reconsideration, and emergency actions.
- Add verified membership and voter-roll management, including standing, roles, delegation/proxy rules if allowed, and eligibility at the time of each action.
- Enforce authorization server-side for every governance action; UI checks should remain convenience only.
- Add immutable audit logs for motion creation, edits, state transitions, votes, comments, admin actions, and rule overrides.
- Add signed or otherwise tamper-evident records for votes and critical governance events.
- Add admin workflows for agendas, meeting minutes, notices, resolutions, committees, officer roles, and publication of official records.
- Add conflict, appeal, moderation, and dispute-resolution workflows.

## Finance Gaps

- Define financial authority rules: who can spend, approve, reconcile, reverse, or administer accounts.
- Add approval workflows for budgets, grants, transfers, reimbursements, and treasury operations.
- Add dual-control or multi-approval requirements for sensitive finance actions.
- Add ledger integrity checks, reconciliation reports, immutable transaction history, and exportable audit reports.
- Separate operational balances, member balances, organizational treasury balances, restricted funds, and administrative accounts clearly.
- Add server-side permission tests for all finance endpoints and actions.

## Security And Reliability

- Complete a threat model covering identity, voting integrity, financial abuse, admin compromise, replay attacks, spam, and insider misuse.
- Add rate limiting, abuse detection, CSRF/session protections where applicable, and stricter input validation.
- Add database constraints and migration tests for governance and finance invariants.
- Add load, concurrency, and race-condition tests for voting, motion state transitions, account balances, and ledger updates.
- Add monitoring, alerting, backups, restore drills, and incident-response procedures.
- Review secrets, environment configuration, Cloudflare/D1/R2/Worker permissions, and production access controls.

## Accessibility And Compliance

- Perform a WCAG accessibility review of governance and finance flows.
- Define retention, privacy, records-access, and deletion policies.
- Review legal/regulatory obligations before using the system for binding governance or finance.

## Testing Priorities

- Keep the new local governance and finance unit tests passing.
- Add server-side authorization and invariant tests before trusting any governance or finance action.
- Add integration tests for complete motion lifecycles, amendment blocking, vote resolution, and finance approval flows.
- Add browser smoke tests for governance, finance, send, receive, login, register, and public profile flows.
- Add performance tests for large voter rolls, large motion histories, and high-volume transaction history.
