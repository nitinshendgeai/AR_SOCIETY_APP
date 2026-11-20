# Billing: interest on back-dated bills runs to the generation date

**Raised by:** the Accounts Agent functional audit, item D-06 (see `docs/ACCOUNTS_AGENT_FUNCTIONAL_AUDIT.md`).
**Status:** open. This needs a decision from the billing module owners and the committee or legal adviser. The Accounts Agent remediation does **not** change any billing calculation.

## What happens

`BillingService` generates a cycle's bills and dates them no later than the cycle start:

- `backend/app/modules/billing/services/billing_service.py`, around line 552: `bill_date = min(cycle.cycle_start, today)`.
- The comment there says: *"Interest on arrears is still counted up to `today`, the day the bills are generated."*

`MaintenanceCalculator.calculate(cycle, today)` passes the **generation date** to `_add_arrears` (`backend/app/modules/billing/services/maintenance_calculator.py`, `_add_arrears`, around lines 675–712). That function computes `days = (bill_date - start).days` and writes `"to": bill_date.isoformat()` into the interest working. Here `bill_date` holds the generation date, not the date printed on the bill.

So when a cycle is generated late (back-dated), interest runs past the bill's own date.

## Observed in the audit

| Item | Value |
|---|---|
| Cycle | October 2026 |
| Bill date | 1 Oct 2026 |
| Bills generated on | 20 Nov 2026 |
| Interest working | 15 Sep 2026 → 20 Nov 2026 (66 days) |
| Interest charged | ₹43.83 |
| Interest up to the bill date (16 days) at the same rate | ₹10.63 |

## Why it matters

- The bill shows interest for days after its own date. A member checking the bill cannot reconcile it.
- The member may also be charged interest again for the same days on the next bill. Whether that happens depends on `arrears_interest_upto`, and needs to be checked.
- Whether interest may run to the generation date is a policy question: it depends on the bye-laws, the General Body resolution and Rule 106C-12. It is not an accounting one.

## What the Accounts Agent now does (no billing change)

The L-CHG-INT-02 finding reads the bill's own interest working and says whether the excess comes from the **rate**, the **period past the bill date**, or both. Where the bill has no working, it says the cause cannot be shown.

## Decisions needed

1. Should interest on a back-dated bill stop at the bill date, or at the generation date?
2. If it should stop at the bill date: change `calculate()`/`_add_arrears()` to use the bill's date for the interest period. Then check `arrears_interest_upto`, so the next bill neither double-counts nor skips any days.
3. If the generation date is intended: print the interest period clearly on the bill. The agent can then be configured to bound interest by the working's own end date.
4. Decide whether bills already issued need a credit note. That is a committee decision, and the change must go through Billing with its normal approvals.
