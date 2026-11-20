"""Statistical detectors over the learned three-month baseline.

Principles
* They compare a voucher with the SOCIETY'S OWN history only (the voucher itself is removed from its baseline).
* They stay silent when the history is too short (see stats.MIN_SAMPLES_*). Nothing is invented.
* A statistic is not an accounting error: results are `statistical_deviation` and capped at MEDIUM, unless the
  deviation is so large that it is a strong signal in itself (>= 10x the learned median, the typical decimal slip),
  in which case it is a `strongly_suspected_anomaly`.
* Every finding explains the calculation (expected, observed, ratio / score, threshold and why that threshold).
"""
from datetime import date
from typing import List, Optional

from app.modules.accounts.models.accounts import RecurringExpense
from app.modules.accounts_agent.services import stats as st
from app.modules.accounts_agent.services.context import Ctx, Draft, fmt, money
from app.modules.accounts_agent.services.learning import Profile, recurring_key

STAT = "statistical_deviation"
SUSPECTED = "strongly_suspected_anomaly"
LARGE_RATIO = 10.0        # >= 10x the median: a decimal-slip scale error is a strong signal on its own
SMALL_RATIO = 0.01        # <= 1 % of the median
MIN_GAP_SAMPLES = 4       # prior occurrences needed before an interval is considered "normal"
BURST_FRACTION = 0.25     # a repeat sooner than a quarter of the normal interval is a burst


def _learning_note(c: Ctx) -> str:
    lab = c.profile.label
    return (" Learning confidence is limited, so treat this with caution." if lab in ("none", "limited") else "")


def _conf(n: int, base: float) -> float:
    """More history → more confident, never above 0.9 for a statistic."""
    return round(min(0.9, base + min(0.2, n / 100)), 2)


def _expense_debit_lines(c: Ctx):
    return [e for e in c.entries if money(e.debit) > 0 and c.meta.get(e.account_id, {}).get("nature") == "expense"]


def detect_amount_outliers(c: Ctx) -> List[Draft]:
    """Unusually large / small expense postings per ledger."""
    out: List[Draft] = []
    thr = float(c.settings.z_threshold)
    for e in _expense_debit_lines(c):
        stats = c.profile.get("account_amount", f"{e.account_id}:dr")
        prior = [s[1] for s in Profile.others((stats or {}).get("samples"), c.voucher.id)]
        if len(prior) < st.MIN_SAMPLES_FOR_Z:
            continue
        x, med_ = float(money(e.debit)), st.med(prior)
        z = st.modified_z(x, prior)
        ratio = x / med_ if med_ else None
        name = c.name(e.account_id)
        ev = {"ledger": name, "amount": x, "prior_count": len(prior), "median": med_, "mad": st.mad(prior),
              "modified_z": z, "z_threshold": thr, "ratio_to_median": ratio, "window": "last 3 months"}
        big = (z is not None and z >= thr) or (z is None and ratio and ratio >= 2)
        if big:
            strong = ratio is not None and ratio >= LARGE_RATIO
            sev = "HIGH" if strong else ("MEDIUM" if (z or 0) >= 2 * thr or (ratio or 0) >= 5 else "LOW")
            how = (f"modified z-score {z:.1f} (threshold {thr})" if z is not None
                   else f"{ratio:.1f}x the median (history shows no spread, so a ratio is used)")
            out.append(Draft("S-AMT-01", "unusual_amount", SUSPECTED if strong else STAT, sev, _conf(len(prior), 0.5 if not strong else 0.65),
                             f"Unusually large posting to {name}",
                             f"{fmt(x)} was posted to '{name}'. Over the last three months the typical posting there is {fmt(med_)} "
                             f"(median of {len(prior)} postings): {how}. The threshold exists so that ordinary month-to-month variation "
                             f"is not flagged.{_learning_note(c)}",
                             f"About {fmt(med_)} (typical range {fmt(stats.get('p10', med_))} – {fmt(stats.get('p90', med_))})",
                             fmt(x), "Check the amount against the bill; correct it if it is a keying error.", ev, subject=str(e.account_id)))
        elif ratio is not None and ratio <= SMALL_RATIO and len(prior) >= 8:
            out.append(Draft("S-AMT-02", "unusual_amount", STAT, "LOW", _conf(len(prior), 0.4),
                             f"Unusually small posting to {name}",
                             f"{fmt(x)} posted to '{name}' is {ratio * 100:.2f}% of the typical {fmt(med_)} (median of {len(prior)} postings).{_learning_note(c)}",
                             f"About {fmt(med_)}", fmt(x), "Confirm it is not a missing digit.", ev, subject=str(e.account_id)))
    return out


def detect_vendor_outliers(c: Ctx) -> List[Draft]:
    v = c.voucher
    if not v.vendor_id or v.voucher_type != "payment":
        return []
    stats = c.profile.get("vendor", str(v.vendor_id))
    prior = [s[1] for s in Profile.others((stats or {}).get("samples"), v.id)]
    x = float(money(v.amount))
    if len(prior) < 4:
        return []
    med_ = st.med(prior)
    z = st.modified_z(x, prior) if len(prior) >= st.MIN_SAMPLES_FOR_Z else None
    ratio = x / med_ if med_ else None
    flagged = (z is not None and z >= float(c.settings.z_threshold)) or \
              (z is None and ratio is not None and (ratio >= 3 or ratio <= 1 / 3))
    if not flagged:
        return []
    name = v.vendor.company_name if v.vendor else "this vendor"
    how = f"modified z-score {z:.1f}" if z is not None else f"{ratio:.1f}x their median payment"
    return [Draft("S-VND-01", "unusual_vendor_payment", STAT, "LOW" if (ratio or 0) < 5 else "MEDIUM", _conf(len(prior), 0.45),
                  f"Unusual payment amount for {name}",
                  f"{fmt(x)} paid to {name}; their usual payment over the last three months is {fmt(med_)} ({len(prior)} earlier payments): {how}.{_learning_note(c)}",
                  f"About {fmt(med_)}", fmt(x), "Verify against the vendor's bill.",
                  {"vendor": name, "amount": x, "median": med_, "prior_count": len(prior), "modified_z": z,
                   "ratio_to_median": ratio}, subject=str(v.vendor_id))]


def _recurring_key(c: Ctx) -> Optional[str]:
    v = c.voucher
    exp = _expense_debit_lines(c)
    if v.voucher_type not in ("payment", "purchase", "journal") or not exp:
        return None
    return recurring_key(v, [e.account_id for e in exp])


def detect_recurring_deviation(c: Ctx) -> List[Draft]:
    """Compare a recurring expense with the amount it normally has."""
    out: List[Draft] = []
    v, tol = c.voucher, float(c.settings.recurring_tolerance_pct) / 100.0
    amount = float(money(v.amount))
    key = _recurring_key(c)
    done_configured = False
    # (a) a standing expense the society configured with a fixed amount
    exp_ids = [e.account_id for e in _expense_debit_lines(c)]
    if exp_ids:
        for r in c.db.query(RecurringExpense).filter(
                RecurringExpense.society_id == v.society_id, RecurringExpense.is_active == True,  # noqa: E712
                RecurringExpense.expense_account_id.in_(exp_ids), RecurringExpense.amount.isnot(None)):
            if r.vendor_id and r.vendor_id != v.vendor_id:
                continue
            exp = float(money(r.amount))
            dev = st.relative_deviation(amount, exp)
            done_configured = True
            if dev is not None and dev >= tol:
                out.append(Draft("S-REC-02", "recurring_deviation", SUSPECTED, "MEDIUM", 0.75,
                                 f"{r.name}: amount differs from the standing amount",
                                 f"Recurring expense '{r.name}' is set up at {fmt(exp)} a month; this voucher is {fmt(amount)} "
                                 f"({dev * 100:.1f}% {'higher' if amount > exp else 'lower'}; tolerance {tol * 100:.0f}%).",
                                 fmt(exp), fmt(amount), "Confirm the new amount (e.g. a revised contract) or correct the voucher.",
                                 {"recurring": r.name, "expected": exp, "actual": amount, "deviation_pct": round(dev * 100, 2),
                                  "tolerance_pct": tol * 100}, subject=str(r.id)))
    # (b) a recurring pattern learned from the last three months
    if key and not done_configured:
        stats = c.profile.get("recurring", key)
        prior = [s[1] for s in Profile.others((stats or {}).get("samples"), v.id)]
        if len(prior) >= st.MIN_SAMPLES_FOR_RECURRING and len({s[2][:7] for s in (stats or {}).get("samples", []) if s[0] != str(v.id)}) >= 2:
            expected = st.med(prior)
            dev = st.relative_deviation(amount, expected)
            if dev is not None and dev >= tol:
                strong = dev >= 1.0
                sev = "HIGH" if strong else ("MEDIUM" if dev >= 0.25 else "LOW")
                out.append(Draft("S-REC-01", "recurring_deviation", SUSPECTED if strong else STAT, sev, _conf(len(prior), 0.55),
                                 "Recurring expense amount changed",
                                 f"This looks like a recurring expense: earlier amounts in the last three months were "
                                 f"{', '.join(fmt(a) for a in prior[-6:])} (median {fmt(expected)}). The current {fmt(amount)} is "
                                 f"{dev * 100:.1f}% {'above' if amount > expected else 'below'} the expected amount (|{fmt(amount)} − {fmt(expected)}| ÷ {fmt(expected)}); "
                                 f"your tolerance is {tol * 100:.0f}%.{_learning_note(c)}",
                                 f"About {fmt(expected)}", fmt(amount),
                                 "Confirm the change is intended (rate revision, extra charges) or correct the voucher.",
                                 {"expected": expected, "actual": amount, "prior_amounts": prior[-12:], "deviation_pct": round(dev * 100, 2),
                                  "tolerance_pct": tol * 100, "key": key.split(":")[0]}, subject=key))
    return out


def detect_frequency(c: Ctx) -> List[Draft]:
    """A payment to the same vendor (or on the same ledger, if no vendor) repeated far sooner than its normal rhythm."""
    v = c.voucher
    exp = _expense_debit_lines(c)
    if v.voucher_type not in ("payment", "purchase") or not exp:
        return []
    vendor_ids = {x for x in [v.vendor_id, *[e.vendor_id for e in c.entries]] if x}
    key = ("vendor", str(next(iter(vendor_ids)))) if vendor_ids else ("account_amount", f"{exp[0].account_id}:dr")
    stats = c.profile.get(*key) or {}
    prior = sorted(date.fromisoformat(s[2]) for s in Profile.others(stats.get("samples"), v.id))
    if len(prior) < MIN_GAP_SAMPLES + 1:
        return []
    gaps = [(b - a).days for a, b in zip(prior, prior[1:])]
    normal = st.med(gaps)
    earlier = [d for d in prior if d <= v.voucher_date]
    if normal < 7 or not earlier:
        return []
    gap = (v.voucher_date - earlier[-1]).days
    if gap < 0 or gap >= normal * BURST_FRACTION:
        return []
    return [Draft("S-FREQ-01", "unusual_frequency", STAT, "LOW", _conf(len(prior), 0.4),
                  "Expense repeated sooner than usual",
                  f"This expense normally recurs about every {normal:.0f} days (median of {len(gaps)} gaps in the last three months); "
                  f"this one came {gap} day(s) after the previous. A repeat inside {BURST_FRACTION * 100:.0f}% of the normal interval is flagged.{_learning_note(c)}",
                  f"About every {normal:.0f} days", f"{gap} day(s) after the last", "Check it is not a duplicate or an advance payment.",
                  {"normal_gap_days": normal, "actual_gap_days": gap, "gaps": gaps[-12:]}, subject=key[1])]


def detect_ledger_mapping(c: Ctx) -> List[Draft]:
    """A vendor whose expenses have consistently gone to one ledger is suddenly posted to another."""
    v = c.voucher
    if not v.vendor_id and not any(e.vendor_id for e in c.entries):
        return []
    vid = str(v.vendor_id or next(e.vendor_id for e in c.entries if e.vendor_id))
    stats = c.profile.get("vendor", vid)
    if not stats:
        return []
    dist = {k: int(n) for k, n in (stats.get("accounts") or {}).items()}
    if c.in_profile():                                    # leave this voucher's own contribution out
        for e in _expense_debit_lines(c):
            if dist.get(str(e.account_id)):
                dist[str(e.account_id)] -= 1
    total = sum(max(n, 0) for n in dist.values())
    if total < 3:
        return []
    top_id, top_n = max(dist.items(), key=lambda kv: kv[1])
    if top_n / total < 0.8:
        return []
    out: List[Draft] = []
    for e in _expense_debit_lines(c):
        if str(e.account_id) != top_id and dist.get(str(e.account_id), 0) == 0:
            name = v.vendor.company_name if v.vendor else "this vendor"
            out.append(Draft("S-MAP-01", "ledger_mapping", SUSPECTED, "MEDIUM", _conf(total, 0.55),
                             "Expense posted to an unusual ledger for this vendor",
                             f"{top_n} of {total} earlier postings for {name} in the last three months ({top_n / total * 100:.0f}%) went to "
                             f"'{c.name(__import__('uuid').UUID(top_id))}'. This voucher posts to '{c.name(e.account_id)}', which this vendor "
                             f"has not been posted to in the window.{_learning_note(c)}",
                             f"Posted to '{c.name(__import__('uuid').UUID(top_id))}'", f"Posted to '{c.name(e.account_id)}'",
                             "Confirm the ledger; re-map the line if it is a mistake.",
                             {"vendor": name, "usual_ledger_id": top_id, "usual_ledger": c.name(__import__('uuid').UUID(top_id)),
                              "usual_share": round(top_n / total, 2), "actual_ledger_id": str(e.account_id), "observations": total},
                             subject=str(e.account_id)))
    return out


def detect_unusual_combination(c: Ctx) -> List[Draft]:
    """A manual voucher's debit/credit combination never seen for this voucher type in the window."""
    v = c.voucher
    if not c.is_manual or v.reversal_of_id or v.voucher_type == "closing" or c.profile.run is None:
        return []
    vt = c.profile.get("voucher_type", v.voucher_type)
    if not vt or vt.get("count", 0) < 10 or c.profile.pairs_for(v.voucher_type) < 2:
        return []
    drs = {str(e.account_id) for e in c.entries if money(e.debit) > 0}
    crs = {str(e.account_id) for e in c.entries if money(e.credit) > 0}
    out: List[Draft] = []
    for d in drs:
        for cr in crs:
            stats = c.profile.get("ledger_pair", f"{v.voucher_type}|{d}|{cr}")
            seen = (stats or {}).get("count", 0) - (1 if c.in_profile() else 0)
            if seen <= 0:
                import uuid
                out.append(Draft("S-PAIR-01", "unexpected_combination", STAT, "LOW", 0.45,
                                 "Debit/credit combination not seen before",
                                 f"Debit '{c.name(uuid.UUID(d))}' with credit '{c.name(uuid.UUID(cr))}' has not been used in any {v.voucher_type} "
                                 f"voucher in the last three months ({vt['count']} such vouchers). Unfamiliar is not wrong — it is flagged only so it is seen once.{_learning_note(c)}",
                                 "A combination used before", "A new combination",
                                 "Confirm the ledgers are the intended ones.", {"debit": c.name(uuid.UUID(d)), "credit": c.name(uuid.UUID(cr)),
                                                                                "voucher_type": v.voucher_type}, subject=f"{d}|{cr}"))
    return out[:3]


def detect_nature_mismatch(c: Ctx) -> List[Draft]:
    v = c.voucher
    if not c.is_manual or v.reversal_of_id:
        return []
    out: List[Draft] = []
    for e in c.entries:
        nature = c.meta.get(e.account_id, {}).get("nature")
        if v.voucher_type == "payment" and money(e.debit) > 0 and nature == "income":
            out.append(Draft("S-NAT-01", "ledger_validation", SUSPECTED, "MEDIUM", 0.6, "Payment debits an income ledger",
                             f"{v.voucher_number} pays money out and debits '{c.name(e.account_id)}', an income ledger. That is correct for a refund "
                             "of income, but often a wrong ledger choice.", "Payments normally debit expense, asset or liability ledgers",
                             f"Debit on income ledger '{c.name(e.account_id)}'", "Confirm it is a refund; otherwise re-map the line.",
                             {"ledger": c.name(e.account_id)}, subject=str(e.account_id)))
        if v.voucher_type == "receipt" and money(e.credit) > 0 and nature == "expense":
            out.append(Draft("S-NAT-02", "ledger_validation", SUSPECTED, "LOW", 0.5, "Receipt credits an expense ledger",
                             f"{v.voucher_number} receives money and credits '{c.name(e.account_id)}', an expense ledger. Fine for a recovery or refund; otherwise likely a wrong ledger.",
                             "Receipts normally credit income, liability or asset ledgers", f"Credit on expense ledger '{c.name(e.account_id)}'",
                             "Confirm it is a recovery; otherwise re-map the line.", {"ledger": c.name(e.account_id)}, subject=str(e.account_id)))
    return out


def detect_type_outlier(c: Ctx) -> List[Draft]:
    """Unusual manual journal adjustment size, against the society's other journals."""
    v = c.voucher
    if v.voucher_type != "journal" or not c.is_manual or v.reversal_of_id:
        return []
    stats = c.profile.get("voucher_type", "journal")
    prior = [s[1] for s in Profile.others((stats or {}).get("samples"), v.id)]
    if len(prior) < st.MIN_SAMPLES_FOR_Z:
        return []
    x = float(money(v.amount))
    z = st.modified_z(x, prior)
    if z is None or z < float(c.settings.z_threshold):
        return []
    return [Draft("S-JRN-02", "unusual_journal", STAT, "LOW", _conf(len(prior), 0.45), "Unusually large journal adjustment",
                  f"Journal of {fmt(x)}; the society's other journals in the last three months have a median of {fmt(st.med(prior))} "
                  f"({len(prior)} journals): modified z-score {z:.1f} (threshold {c.settings.z_threshold}).{_learning_note(c)}",
                  f"About {fmt(st.med(prior))}", fmt(x), "Confirm the adjustment is supported.",
                  {"amount": x, "median": st.med(prior), "modified_z": z, "prior_count": len(prior)})]


STATISTICAL = (detect_amount_outliers, detect_vendor_outliers, detect_recurring_deviation, detect_frequency,
               detect_ledger_mapping, detect_unusual_combination, detect_nature_mismatch, detect_type_outlier)


from app.modules.accounts_agent.services.bill_checks import detect_bill_month_change  # noqa: E402

STATISTICAL = STATISTICAL + (detect_bill_month_change,)
