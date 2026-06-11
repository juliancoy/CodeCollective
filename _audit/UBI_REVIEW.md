# DENA UBI — logic review & data

**Dena** (currency code `DEM`) is the unit of the Code Collective democratic economy.
The production UBI runs in the **org-worker** Cloudflare Worker (`portal/org-worker/src/index.ts`),
driven by a cron trigger every minute (`"* * * * *"` → `scheduled()` → `runUbiTick`).
`portal/ubi/*.py` is legacy reference only.

## Model

Two balances per account (`ledger_accounts`):
- `dena_balance` — high-precision *accrual* bucket (continuous minting).
- `balance` — spendable balance, settled in whole cents.

Settings (`ubi_runtime_settings`, singleton id=1):
| field | seed value | meaning |
|---|---|---|
| `interval_seconds` | 1209600 | payout cadence = 14 days |
| `dena_annual` | 1 | Dena minted per eligible account per year (**placeholder**) |
| `dena_precision` | 6 | accrual rounding precision |
| `entity_types` | `["individual"]` | which account types receive UBI |

## How a tick works (`runUbiTick`)

1. **Claim** the run: `run_key = startedAt[:16]` (minute granularity), `INSERT OR IGNORE` into
   `ubi_tick_runs`. If already present → `status:"skipped"` (idempotency / no double-pay).
2. **Elapsed**: `max(0, now − last_tick_at)` seconds.
3. **Accrue**: `accrued = round(dena_annual × elapsed / 31_536_000, precision)` added to
   `dena_balance` of **every account whose `entity_type ∈ entity_types`**.
4. **Pay** (per account) when `dena_balance ≥ 0.01` AND `is_eligible=1` AND
   `next_payment_date ≤ today`: move `floor(dena_balance, cents)` from `dena_balance` → `balance`,
   write a `UBI_PAYMENT` ledger transaction (minted: `from_account = NULL`), set
   `next_payment_date = now + cadence`, accumulate `total_payments_received`.
5. Update `last_tick_at`; record run stats.

So: **accrue continuously, sweep whole cents to spendable balance every 14 days.** Sub-cent
remainder stays in `dena_balance`. UBI is monetary expansion by design (new Dena minted each payout).

## Empirical validation (real local D1)

Unit tests: `npx tsx --test test/org-worker.test.ts` → **19/19 pass** (5 UBI-specific).

Live tick against seeded data (temporarily set rate to 1 Dena/min, last tick ~134 min prior,
alice due / bob not):

| account | type | before → after balance | dena_balance | paid |
|---|---|---|---|---|
| alice | individual | 1200 → **1334.4** | 0 (swept) | 134.4 ✓ due |
| bob | individual | 980 → 980 | **134.4** (held) | 0 — cadence not due ✓ |
| civic-fund | nonprofit | 50000 → 50000 | 0 | 0 — wrong entity_type ✓ |
| code-collective | nonprofit | 25000 → 25000 | 0 | 0 — wrong entity_type ✓ |

Run record: `eligible_accounts=2, payout_count=1, accrued=134.4, paid=134.4`. A second tick in the
same minute returned `skipped` (no double-pay). All four behaviors (accrual scope, cadence gating,
payout mechanics, idempotency) confirmed correct. (DB restored to seed afterward.)

## Findings

**Correct / sound**
- Cadence gating, entity-type scoping, whole-cent settlement with preserved sub-cent remainder.
- Idempotent runs (minute-keyed) — verified no double payout.
- Crash-resilient: `last_tick_at` only advances on success, so elapsed (and accrual) catches up.
- Mutating routes (`PATCH /ubi/settings`, `POST /ubi/tick`, `tick-status`) are admin-gated; inputs clamped (cadence ≤ 1yr, precision ≤ 12, dena_annual ≥ 0).

**Issues**
1. **[Medium] Money stored as `REAL` (float64)** — `balance`, `dena_balance`, `amount` are floats.
   Accumulating currency in float risks sub-cent dust and non-associative sums across the ledger.
   Use integer minor units (store cents as INTEGER) or a fixed-decimal representation.
2. **[Medium] Accrual ignores `is_eligible`** — accrual filters by `entity_type` only; only *payout*
   checks `is_eligible`. A disabled account keeps minting into `dena_balance` and, if re-enabled,
   receives the full back-paid lump on the next due tick. Either also gate accrual on `is_eligible`,
   or document this as intended "pause withdrawals, keep accruing."
3. **[Low] Per-tick rounding bias at small `dena_annual`** — with the seeded `dena_annual=1` and
   minute ticks, raw accrual 1.9026e-6 rounds (precision 6) to 0.000002 every tick → ~**+5%/yr**
   over-accrual. Negligible at realistic annual amounts (hundreds+), but the default is mis-calibrated.
4. **[Low] `GET /ubi/eligibility` `estimated_amount` = `dena_annual`** — reports the *annual* figure,
   not the per-cadence payout (≈ accrued `dena_balance`). Misleading to users.
5. **[Low] `POST /ubi/tick` `scheduled_time` is unbounded** — an admin passing a far-future timestamp
   sets `last_tick_at` ahead of real time, stalling accrual (elapsed clamps to 0) until wall-clock
   catches up. Bound it to ~now.

## Data availability
- The figures above are the **migration seed / local** values. Production `dena_annual` and the live
  ledger are behind authenticated admin endpoints (`/api/ubi/*` return 401 unauthenticated) and were
  not retrievable from here. With an admin token on the local stack (or prod), `GET /api/ubi/settings`,
  `/api/ubi/tick-status`, and `/api/ubi/eligibility` expose the live numbers.
