"""Engine B (legal & bye-law compliance) and the residential-society accounting checks, run as a society scan.

Engine A (services/rules.py, services/anomaly.py) still analyses each voucher as it is posted. This scan looks at the
society as a whole — charge configuration, bills, member dues, funds, vendor contracts, budgets, resolutions and the
compliance calendar — and stores its results in the same findings table (engine = "legal" or "accounting").

Principles enforced here:
- the strength of a legal finding comes from registry.classify(): unverified law gives POTENTIAL_NON_COMPLIANCE at most,
  a model bye-law gives an ADVISORY_OBSERVATION, a blocking review prevents a confirmed violation;
- each transaction is judged by the rule in force on ITS date (registry.resolve(topic, date));
- a statistic or a budget overrun is never presented as a legal violation;
- the scan never changes a voucher, bill, receipt, vendor or balance; the only rows it writes are the agent's own
  (findings, legal reviews, the compliance calendar, and its record of vendor bank details).
"""
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.flat import Flat
from app.models.wing import Wing
from app.modules.accounts.models.accounts import Account, Voucher, VoucherEntry
from app.modules.accounts.services.accounts_service import fiscal_year, fiscal_year_bounds
from app.modules.accounts_agent.legal import calendar as compliance_calendar
from app.modules.accounts_agent.legal import registry, resolutions
from app.modules.accounts_agent.legal.models import (
    OPEN_REVIEW_STATUSES, OPERATIVE_DOCUMENT_STATUSES, VERIFIED, BudgetLine, ComplianceItem, LegalDocument,
    LegalReview, SocietyResolution,
)
from app.modules.accounts_agent.models.agent import AgentFinding
from app.modules.accounts_agent.services import audit
from app.modules.billing.models.billing import (
    BillingCycle, BillStatus, ChargeBasis, ChargeType, InvoiceLineItem, MaintenanceBill, MaintenanceChargeConfig,
    MaintenanceSettings, PaymentReceipt,
)
from app.utils.local_time import society_today

logger = logging.getLogger(__name__)
D0 = Decimal("0")
FUND_KEYS = ("reserve_fund", "sinking_fund", "repair_fund", "major_repair_fund", "education_fund", "building_fund")
REPAIR_KEYS = ("repairs_building", "repairs_electrical", "repairs_plumbing", "repairs_general")
LIVE_BILL = (BillStatus.GENERATED, BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.PAID, BillStatus.OVERDUE)
PREFIX = "SCAN:"


def money(v) -> Decimal:
    return Decimal(str(v if v is not None else 0)).quantize(Decimal("0.01"))


def inr(v) -> str:
    return f"₹{money(v):,.2f}"


@dataclass
class LDraft:
    rule_code: str
    engine: str
    category: str
    compliance_category: Optional[str]
    finding_class: str
    severity: str
    confidence: float
    title: str
    explanation: str
    expected: str = ""
    actual: str = ""
    recommended: str = ""
    evidence: dict = field(default_factory=dict)
    subject: str = ""
    legal_rule_code: Optional[str] = None
    legal_source: Optional[dict] = None
    voucher_id: Optional[UUID] = None
    transaction_ref: Optional[str] = None
    voucher_date: Optional[date] = None
    flat_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None

    @property
    def key(self) -> str:
        return f"{PREFIX}{self.rule_code}:{self.subject}"[:200]


class Scan:
    def __init__(self, db: Session, society_id: UUID):
        self.db, self.sid = db, society_id
        self.today = society_today(db, society_id)
        self.accounts = {a.system_key: a for a in db.query(Account).filter(Account.society_id == society_id,
                                                                            Account.system_key.isnot(None))}
        self.account_by_id = {a.id: a for a in db.query(Account).filter(Account.society_id == society_id)}
        self.settings = db.query(MaintenanceSettings).filter(MaintenanceSettings.society_id == society_id).first()
        self._rules: Dict[tuple, registry.Applicable] = {}
        self._flat_labels: Optional[Dict[UUID, str]] = None

    def rule(self, topic: str, on: date) -> registry.Applicable:
        k = (topic, on)
        if k not in self._rules:
            self._rules[k] = registry.resolve(self.db, self.sid, topic, on)
        return self._rules[k]

    def legal(self, code, category, ccat, app: registry.Applicable, title, explanation, *, deterministic=True,
              severity=None, confidence=None, **kw) -> LDraft:
        cls = registry.classify(app, deterministic=deterministic)
        conf = confidence if confidence is not None else (0.95 if cls.startswith("CONFIRMED") else
                                                          0.6 if cls == "POTENTIAL_NON_COMPLIANCE" else 0.4)
        sev = severity or (app.rule.severity if app.rule else "MEDIUM")
        if cls == "ADVISORY_OBSERVATION":
            sev = "LOW" if sev in ("CRITICAL", "HIGH", "MEDIUM") else sev
        return LDraft(code, "legal", category, ccat, cls, sev, conf, title, explanation,
                      legal_rule_code=app.rule.rule_code if app.rule else None,
                      legal_source=registry.source_ref(app.rule, app), **kw)

    def flat_label(self, flat_id) -> str:
        if self._flat_labels is None:
            self._flat_labels = {f.id: f"{w.name}-{f.flat_number}" for f, w in
                                 self.db.query(Flat, Wing).join(Wing, Wing.id == Flat.wing_id).filter(Wing.society_id == self.sid)}
        return self._flat_labels.get(flat_id, "a flat")

    def configs(self) -> List[MaintenanceChargeConfig]:
        t = self.today
        return [c for c in self.db.query(MaintenanceChargeConfig).options(selectinload(MaintenanceChargeConfig.element))
                .filter(MaintenanceChargeConfig.society_id == self.sid, MaintenanceChargeConfig.is_active == True)  # noqa: E712
                if not (c.effective_to and c.effective_to < t)]

    def vouchers(self, since: date, types=None):
        q = (self.db.query(Voucher).options(selectinload(Voucher.entries))
             .filter(Voucher.society_id == self.sid, Voucher.is_cancelled == False, Voucher.voucher_date >= since,  # noqa: E712
                     Voucher.approval_status == "approved", Voucher.voucher_type != "closing"))
        if types:
            q = q.filter(Voucher.voucher_type.in_(types))
        return q.all()


# ── Charges (Rule 106C-12) ──────────────────────────────────────────────────────────────────────────────────────────

def chk_interest_setting(s: Scan) -> List[LDraft]:
    if not s.settings:
        return []
    app = s.rule("charges.interest_on_arrears.max_rate_pct", s.today)
    cap, rate = app.effective_value, money(s.settings.interest_rate_pct)
    if cap is None or rate <= Decimal(str(cap)):
        return []
    return [s.legal("L-CHG-INT-01", "charges", "interest_on_arrears", app,
                    f"Interest rate on arrears ({rate}% p.a.) is above the applicable ceiling ({cap}% p.a.)",
                    f"The society charges {rate}% p.a. on overdue dues. The rule applicable today "
                    f"({app.rule.rule_code} v{app.rule.version}) sets a ceiling of {cap}% p.a. simple interest.",
                    expected=f"≤ {cap}% p.a.", actual=f"{rate}% p.a.",
                    recommended="Check the registered bye-law and General Body resolution on interest; if the ceiling "
                                "is confirmed, lower the rate in Billing → Settings from the next bill.",
                    evidence={"configured_rate_pct": str(rate), "ceiling_pct": cap,
                              "calculation": f"{rate} > {cap}"}, subject="settings")]


def chk_non_occupancy_setting(s: Scan) -> List[LDraft]:
    if not s.settings:
        return []
    app = s.rule("charges.non_occupancy.max_pct", s.today)
    cap, pct = app.effective_value, money(s.settings.non_occupancy_pct)
    if cap is None or pct <= Decimal(str(cap)):
        return []
    return [s.legal("L-CHG-NOC-01", "charges", "non_occupancy", app,
                    f"Non-occupancy charge ({pct}% of service charges) is above the applicable ceiling ({cap}%)",
                    f"Flats let out pay {pct}% of service charges as non-occupancy charges; the applicable rule "
                    f"({app.rule.rule_code}) caps it at {cap}% of service charges.",
                    expected=f"≤ {cap}%", actual=f"{pct}%",
                    recommended="Confirm the General Body resolution and the verified rule, then correct the rate.",
                    evidence={"configured_pct": str(pct), "ceiling_pct": cap}, subject="settings")]


def chk_non_occupancy_bills(s: Scan) -> List[LDraft]:
    """On recent bills: the non-occupancy line compared with the same bill's service-charge lines, by the rule in force
    on the bill date."""
    out = []
    service_names = {c.name for c in s.configs() if c.is_service_charge}
    since = s.today - timedelta(days=400)
    bills = (s.db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
             .filter(MaintenanceBill.society_id == s.sid, MaintenanceBill.bill_status.in_(LIVE_BILL),
                     MaintenanceBill.bill_date >= since).all())
    for b in bills:
        noc = sum((money(li.amount) for li in b.line_items if "non-occupancy" in li.description.lower()
                   or "non occupancy" in li.description.lower()), D0)
        if not noc:
            continue
        base = sum((money(li.amount) for li in b.line_items if li.description in service_names), D0)
        app = s.rule("charges.non_occupancy.max_pct", b.bill_date)
        cap = app.effective_value
        if cap is None or not base:
            continue
        limit = (base * Decimal(str(cap)) / 100).quantize(Decimal("0.01"))
        if noc > limit + Decimal("1.00"):
            out.append(s.legal("L-CHG-NOC-02", "charges", "non_occupancy", app,
                               f"Non-occupancy charge on {b.invoice_number} exceeds {cap}% of service charges",
                               f"Bill {b.invoice_number} for {s.flat_label(b.flat_id)} charges {inr(noc)} as non-occupancy "
                               f"charges on service charges of {inr(base)}; {cap}% would be {inr(limit)}.",
                               expected=f"≤ {inr(limit)}", actual=inr(noc),
                               recommended="Re-check the non-occupancy rate used for this bill; raise a credit note if "
                                           "the excess is confirmed.",
                               evidence={"bill": b.invoice_number, "service_charges": str(base), "non_occupancy": str(noc),
                                         "cap_pct": cap, "calculation": f"{base} × {cap}% = {limit}"},
                               subject=str(b.id), flat_id=b.flat_id, transaction_ref=b.invoice_number,
                               voucher_date=b.bill_date))
    return out


def chk_charge_apportionment(s: Scan) -> List[LDraft]:
    out = []
    app = s.rule("charges.apportionment", s.today)
    allowed = (app.rule.calculation_method or {}).get("allowed_bases", {}) if app.rule else {}
    for c in s.configs():
        code = c.element.code if c.element else None
        if c.charge_type == ChargeType.PARKING:
            code = code or "parking"
        if code not in allowed:
            continue
        basis = c.basis.value if hasattr(c.basis, "value") else str(c.basis)
        if basis in allowed[code]:
            continue
        out.append(s.legal("L-CHG-APP-01", "charges", "charge_apportionment", app,
                           f"'{c.name}' is apportioned {basis.replace('_', ' ')}, not as the rule provides",
                           f"The charge head '{c.name}' is shared among flats on the basis '{basis}'. The apportionment "
                           f"rule ({app.rule.rule_code}) provides {', '.join(allowed[code])} for this kind of charge. "
                           "Not every charge is shared equally per flat (e.g. property tax as levied, water by inlets).",
                           expected=" / ".join(allowed[code]), actual=basis, severity="MEDIUM",
                           recommended="Check the registered bye-law and the General Body resolution on how this head "
                                       "is shared; change the basis on the charge head if needed.",
                           evidence={"charge_head": c.name, "element": code, "basis": basis, "allowed": allowed[code]},
                           subject=str(c.id)))
    return out


def chk_fund_rates(s: Scan) -> List[LDraft]:
    out = []
    configs = s.configs()
    sinking = [c for c in configs if c.charge_type == ChargeType.SINKING_FUND]
    app = s.rule("funds.sinking_fund.rate", s.today)
    minimum = app.effective_value
    for c in sinking:
        basis = c.basis.value if hasattr(c.basis, "value") else str(c.basis)
        rate = money(c.default_amount)
        if basis == ChargeBasis.CONSTRUCTION_COST_PCT.value:
            if minimum is not None and rate < Decimal(str(minimum)):
                out.append(s.legal("L-FND-SNK-01", "funds", "fund_contribution", app,
                                   f"Sinking fund contribution {rate}% p.a. is below the minimum {minimum}%",
                                   f"'{c.name}' collects {rate}% p.a. of construction cost; the applicable rule "
                                   f"({app.rule.rule_code}) requires at least {minimum}% p.a.",
                                   expected=f"≥ {minimum}% p.a. of construction cost", actual=f"{rate}% p.a.",
                                   recommended="Confirm the rate with the verified rule and the General Body; correct "
                                               "the charge head from the next bill.",
                                   evidence={"rate_pct": str(rate), "minimum_pct": minimum}, subject=str(c.id)))
        else:
            out.append(LDraft("L-FND-SNK-02", "legal", "funds", "fund_contribution", "ADVISORY_OBSERVATION", "LOW", 0.4,
                              f"Sinking fund '{c.name}' is levied on a different basis ({basis.replace('_', ' ')})",
                              f"The sinking-fund rule is stated as a % of the architect-certified construction cost; this "
                              f"head uses '{basis}'. That may be what the society's registered bye-laws provide — check "
                              "that the amount collected is at least what the rule requires.",
                              expected="% of construction cost", actual=basis,
                              recommended="Compare a year's collection with the construction-cost minimum.",
                              evidence={"basis": basis, "rate": str(rate)}, subject=str(c.id),
                              legal_rule_code=app.rule.rule_code if app.rule else None,
                              legal_source=registry.source_ref(app.rule, app)))
    if not sinking and s.configs():
        out.append(LDraft("L-FND-SNK-03", "legal", "funds", "fund_contribution", "ADVISORY_OBSERVATION", "LOW", 0.4,
                          "No sinking fund contribution is being billed",
                          "None of the active charge heads is a sinking fund contribution.",
                          recommended="Check whether the registered bye-laws require a sinking fund contribution.",
                          subject="none", legal_rule_code=app.rule.rule_code if app.rule else None,
                          legal_source=registry.source_ref(app.rule, app)))
    rep = s.rule("funds.repair_fund.rate", s.today)
    ref = rep.effective_value
    for c in configs:
        if c.charge_type != ChargeType.REPAIR_FUND or ref is None:
            continue
        basis = c.basis.value if hasattr(c.basis, "value") else str(c.basis)
        if basis == ChargeBasis.CONSTRUCTION_COST_PCT.value and money(c.default_amount) < Decimal(str(ref)):
            out.append(s.legal("L-FND-REP-01", "funds", "fund_contribution", rep,
                               f"Repair fund contribution {money(c.default_amount)}% p.a. is below the reference {ref}%",
                               f"'{c.name}' collects {money(c.default_amount)}% p.a. of construction cost; the model "
                               f"bye-law reference figure is {ref}% p.a.", evidence={"rate_pct": str(money(c.default_amount))},
                               subject=str(c.id)))
    return out


# ── Bills and member ledgers (accounting) ──────────────────────────────────────────────────────────────────────────

def _bills(s: Scan, since: date):
    return (s.db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
            .filter(MaintenanceBill.society_id == s.sid, MaintenanceBill.bill_status.in_(LIVE_BILL),
                    MaintenanceBill.bill_date >= since).all())


def chk_bill_integrity(s: Scan) -> List[LDraft]:
    out = []
    bills = _bills(s, s.today - timedelta(days=550))
    by_flat_cycle = defaultdict(list)
    for b in bills:
        by_flat_cycle[(b.flat_id, b.cycle_id)].append(b)
        expect = money(b.total_amount) + money(b.penalty_amount) - money(b.paid_amount)
        if money(b.outstanding) != expect:
            out.append(LDraft("A-BIL-OUT-01", "accounting", "member_ledger", None, "CONFIRMED_ACCOUNTING_ERROR", "HIGH", 0.95,
                              f"Outstanding on {b.invoice_number} does not equal total − paid",
                              f"Bill {b.invoice_number} ({s.flat_label(b.flat_id)}) shows {inr(b.outstanding)} outstanding, "
                              f"but total {inr(b.total_amount)} + interest {inr(b.penalty_amount)} − paid {inr(b.paid_amount)} "
                              f"= {inr(expect)}.", expected=inr(expect), actual=inr(b.outstanding),
                              recommended="Re-allocate the receipts against this bill from Billing so the balance is recomputed.",
                              evidence={"total": str(money(b.total_amount)), "penalty": str(money(b.penalty_amount)),
                                        "paid": str(money(b.paid_amount)), "outstanding": str(money(b.outstanding)),
                                        "calculation": f"{money(b.total_amount)} + {money(b.penalty_amount)} − {money(b.paid_amount)} = {expect}"},
                              subject=str(b.id), flat_id=b.flat_id, transaction_ref=b.invoice_number, voucher_date=b.bill_date))
    for (flat_id, cycle_id), rows in by_flat_cycle.items():
        if len(rows) > 1:
            rows.sort(key=lambda b: b.created_at)
            out.append(LDraft("A-BIL-DUP-01", "accounting", "member_ledger", None, "CONFIRMED_ACCOUNTING_ERROR", "HIGH", 0.9,
                              f"{len(rows)} live bills for {s.flat_label(flat_id)} in the same billing cycle",
                              f"Bills {', '.join(b.invoice_number for b in rows)} were raised on the same flat for the same "
                              "cycle. A flat normally has one bill per cycle.",
                              expected="1 bill per flat per cycle", actual=f"{len(rows)} bills",
                              recommended="Cancel the duplicate bill(s) from Billing (this reverses their postings).",
                              evidence={"bills": [b.invoice_number for b in rows], "cycle_id": str(cycle_id)},
                              subject=f"{flat_id}:{cycle_id}", flat_id=flat_id, transaction_ref=rows[-1].invoice_number,
                              voucher_date=rows[-1].bill_date))
    return out


def chk_bill_allocation(s: Scan) -> List[LDraft]:
    """A charge head shared equally per flat must carry the same rate on every flat's bill in one cycle."""
    out = []
    equal = {c.name: c for c in s.configs() if not c.parking_zone_id and
             (c.basis.value if hasattr(c.basis, "value") else str(c.basis)) in ("fixed", "budget_equal")
             and not c.applicable_flat_types}
    if not equal:
        return out
    cycles = (s.db.query(BillingCycle).filter(BillingCycle.society_id == s.sid,
                                              BillingCycle.cycle_start >= s.today - timedelta(days=200)).all())
    for cy in cycles:
        rates = defaultdict(list)
        for b in s.db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items)).filter(
                MaintenanceBill.cycle_id == cy.id, MaintenanceBill.bill_status.in_(LIVE_BILL)):
            if b.period_start and b.period_end and (b.period_start != cy.cycle_start or b.period_end != cy.cycle_end):
                continue                                  # a part-period / catch-up bill legitimately differs
            for li in b.line_items:
                if li.description in equal:
                    rates[li.description].append((money(li.unit_rate), b))
        for name, rows in rates.items():
            common = Counter(r for r, _ in rows).most_common(1)[0][0]
            odd = [(r, b) for r, b in rows if r != common]
            if odd and len(rows) >= 3:
                out.append(LDraft("A-BIL-ALC-01", "accounting", "maintenance_billing", "charge_apportionment",
                                  "SUSPECTED_ACCOUNTING_ANOMALY", "MEDIUM", 0.75,
                                  f"'{name}' was billed at different rates in {cy.name}",
                                  f"'{name}' is shared equally per flat, but {len(odd)} of {len(rows)} bills in {cy.name} "
                                  f"charge a different rate from the usual {inr(common)}: "
                                  + ", ".join(f"{s.flat_label(b.flat_id)} {inr(r)}" for r, b in odd[:10]) + ".",
                                  expected=f"{inr(common)} on every full-period bill", actual="different rates",
                                  recommended="Check the flat-level overrides or the bill; correct by credit/debit note.",
                                  evidence={"cycle": cy.name, "usual_rate": str(common),
                                            "flats": [{"flat": s.flat_label(b.flat_id), "rate": str(r), "bill": b.invoice_number}
                                                      for r, b in odd[:50]]},
                                  subject=f"{cy.id}:{name}"[:120], flat_id=odd[0][1].flat_id if len(odd) == 1 else None))
    return out


def interest_cause(bill, cap) -> dict:
    """Read the bill's own interest working (what the billing calculator printed on the bill) and say WHY the interest
    is high (D-06 of the functional audit): a rate above the ceiling, an accrual period that runs past the bill date,
    both, or — without a working — that the cause cannot be shown. Only explains; never recalculates the bill."""
    import json
    try:
        rows = json.loads(bill.interest_working) if bill.interest_working else []
    except (ValueError, TypeError):
        rows = []
    if not rows:
        return {"cause": "UNKNOWN", "rows": [],
                "explanation": "The bill carries no interest working, so whether the rate or the period is wrong cannot be "
                               "shown from the bill.",
                "recommended": "Recompute the interest for this flat; issue a credit note for any excess."}
    checked, late, high = [], [], []
    for r in rows:
        try:
            rate = Decimal(str(r.get("rate", "0")).replace("%", "").strip() or "0")
            start, end = date.fromisoformat(r["from"]), date.fromisoformat(r["to"])
        except (KeyError, ValueError, ArithmeticError):
            continue
        extra = max((end - bill.bill_date).days, 0)
        row = {"bill": r.get("bill"), "from": r["from"], "to": r["to"], "days": r.get("days"), "rate": str(rate),
               "days_after_bill_date": extra}
        checked.append(row)
        if extra:
            late.append(row)
        if cap is not None and rate > Decimal(str(cap)):
            high.append(row)
    parts = []
    if high:
        parts.append(f"The working applies {', '.join(sorted({h['rate'] for h in high}))}% p.a., above the {cap}% ceiling.")
    if late:
        worst = max(late, key=lambda x: x["days_after_bill_date"])
        parts.append(f"The working counts interest up to {worst['to']}, {worst['days_after_bill_date']} day(s) after the "
                     f"bill date ({bill.bill_date}): the accrual period, not only the rate, explains the excess.")
    cause = "RATE_AND_PERIOD" if (high and late) else "RATE" if high else "PERIOD" if late else "UNKNOWN"
    if cause == "UNKNOWN":
        parts.append("The working's rate and dates are within limits, so the difference lies elsewhere (e.g. the "
                     "principal it was charged on).")
    rec = {"PERIOD": "Check how Billing dates the interest period (it should not run past the bill date); recompute "
                     "this flat's interest and issue a credit note for the excess.",
           "RATE": "Correct the interest rate in the billing settings; recompute and credit the excess.",
           "RATE_AND_PERIOD": "Correct the rate and the interest period in Billing; recompute and credit the excess."
           }.get(cause, "Recompute the interest for this flat; issue a credit note for any excess.")
    return {"cause": cause, "rows": checked, "explanation": " ".join(parts), "recommended": rec}


def chk_bill_interest(s: Scan) -> List[LDraft]:
    """Interest charged on a bill compared with the most it could be at the ceiling in force on the bill date."""
    out = []
    for b in _bills(s, s.today - timedelta(days=400)):
        interest = sum((money(li.amount) for li in b.line_items
                        if li.charge_type == ChargeType.PENALTY and "interest" in li.description.lower()), D0)
        if not interest:
            continue
        app = s.rule("charges.interest_on_arrears.max_rate_pct", b.bill_date)
        cap = app.effective_value
        arrears = money(b.previous_dues)
        if arrears <= 0:
            out.append(LDraft("A-BIL-INT-02", "accounting", "member_ledger", "interest_on_arrears",
                              "SUSPECTED_ACCOUNTING_ANOMALY", "MEDIUM", 0.7,
                              f"Interest charged on {b.invoice_number} with no arrears",
                              f"{s.flat_label(b.flat_id)} was charged {inr(interest)} interest but the bill shows no "
                              "previous dues.", expected="No interest without arrears", actual=inr(interest),
                              recommended="Check the interest working on the bill; reverse it if the flat had no dues.",
                              evidence={"interest": str(interest), "previous_dues": str(arrears)}, subject=str(b.id),
                              flat_id=b.flat_id, transaction_ref=b.invoice_number, voucher_date=b.bill_date))
            continue
        if cap is None:
            continue
        earliest = (s.db.query(func.min(MaintenanceBill.due_date))
                    .filter(MaintenanceBill.society_id == s.sid, MaintenanceBill.flat_id == b.flat_id,
                            MaintenanceBill.bill_status.in_(LIVE_BILL), MaintenanceBill.due_date < b.bill_date,
                            MaintenanceBill.id != b.id).scalar())
        days = max((b.bill_date - earliest).days, 0) if earliest else 0
        most = (arrears * Decimal(str(cap)) / 100 * Decimal(days) / Decimal(365)).quantize(Decimal("0.01"))
        if interest > most + Decimal("1.00"):
            cause = interest_cause(b, cap)
            title = {"PERIOD": f"Interest on {b.invoice_number} runs past the bill date",
                     "RATE": f"Interest on {b.invoice_number} uses a rate above {cap}% p.a.",
                     "RATE_AND_PERIOD": f"Interest on {b.invoice_number}: rate above {cap}% p.a. and period past the bill date",
                     }.get(cause["cause"], f"Interest on {b.invoice_number} is more than {cap}% p.a. on the arrears could give")
            out.append(s.legal("L-CHG-INT-02", "charges", "interest_on_arrears", app, title,
                               f"{s.flat_label(b.flat_id)} was charged {inr(interest)} interest. Even if all arrears of "
                               f"{inr(arrears)} had been overdue since the earliest due date ({earliest}, {days} days), "
                               f"{cap}% p.a. simple interest up to the bill date would be at most {inr(most)}. "
                               + cause["explanation"],
                               deterministic=False, expected=f"≤ {inr(most)}", actual=inr(interest),
                               recommended=cause["recommended"],
                               evidence={"interest": str(interest), "arrears": str(arrears), "days": days, "cap_pct": cap,
                                         "calculation": f"{arrears} × {cap}% × {days}/365 = {most}",
                                         "cause": cause["cause"], "working_checked": cause["rows"]},
                               subject=str(b.id), flat_id=b.flat_id, transaction_ref=b.invoice_number,
                               voucher_date=b.bill_date))
    return out


def chk_duplicate_receipts(s: Scan) -> List[LDraft]:
    out = []
    rows = (s.db.query(PaymentReceipt).filter(PaymentReceipt.society_id == s.sid, PaymentReceipt.is_reversed == False,  # noqa: E712
                                              PaymentReceipt.transaction_ref.isnot(None),
                                              PaymentReceipt.payment_date >= s.today - timedelta(days=400)).all())
    groups = defaultdict(list)
    for r in rows:
        if r.transaction_ref.strip():
            groups[(r.flat_id, r.transaction_ref.strip().upper(), money(r.amount))].append(r)
    for (flat_id, ref, amt), rs in groups.items():
        if len(rs) > 1:
            out.append(LDraft("A-RCP-DUP-01", "accounting", "member_ledger", None, "SUSPECTED_ACCOUNTING_ANOMALY", "HIGH", 0.85,
                              f"The same payment ({ref}) is receipted {len(rs)} times for {s.flat_label(flat_id)}",
                              f"Receipts {', '.join(r.receipt_number for r in rs)} carry the same transaction reference and "
                              f"amount {inr(amt)}.", expected="One receipt per payment", actual=f"{len(rs)} receipts",
                              recommended="Check the bank statement; reverse the duplicate receipt if confirmed.",
                              evidence={"receipts": [r.receipt_number for r in rs], "reference": ref, "amount": str(amt)},
                              subject=f"{flat_id}:{ref}"[:120], flat_id=flat_id, transaction_ref=rs[-1].receipt_number,
                              voucher_date=rs[-1].payment_date))
    return out


# ── Vendors and expenditure approvals ──────────────────────────────────────────────────────────────────────────────

def chk_vendor_invoices(s: Scan) -> List[LDraft]:
    from app.modules.vendor.models.vendor import Vendor, VendorInvoice
    out = []
    inv = (s.db.query(VendorInvoice).filter(VendorInvoice.society_id == s.sid, VendorInvoice.is_active == True).all())  # noqa: E712
    groups = defaultdict(list)
    for i in inv:
        groups[(i.vendor_id, (i.invoice_number or "").strip().upper())].append(i)
    names = {v.id: v.company_name for v in s.db.query(Vendor).filter(Vendor.society_id == s.sid)}
    for (vid, num), rows in groups.items():
        if num and len(rows) > 1:
            out.append(LDraft("A-VEN-DUP-01", "accounting", "vendor_audit", None, "SUSPECTED_ACCOUNTING_ANOMALY", "HIGH", 0.85,
                              f"Invoice {num} of {names.get(vid, 'a vendor')} is recorded {len(rows)} times",
                              f"The vendor's invoice number {num} appears on {len(rows)} bills totalling "
                              f"{inr(sum(money(r.total_amount) for r in rows))}. A repeated invoice number usually means a "
                              "duplicate bill.", expected="Each vendor invoice recorded once", actual=f"{len(rows)} records",
                              recommended="Compare the bills; cancel the duplicate before it is paid twice.",
                              evidence={"invoice_number": num, "amounts": [str(money(r.total_amount)) for r in rows],
                                        "paid": [str(money(r.paid_amount)) for r in rows]},
                              subject=f"{vid}:{num}"[:120], vendor_id=vid))
    # Manual vendor payments with no supplier bill on record.
    for v in s.vouchers(s.today - timedelta(days=365), ("payment",)):
        vid = v.vendor_id or next((e.vendor_id for e in v.entries if e.vendor_id), None)
        if v.source_type or not vid or (v.reference or "").strip():
            continue
        lo, hi = v.voucher_date - timedelta(days=90), v.voucher_date + timedelta(days=15)
        bill = (s.db.query(VendorInvoice.id).filter(VendorInvoice.society_id == s.sid, VendorInvoice.vendor_id == vid,
                                                    VendorInvoice.invoice_date.between(lo, hi),
                                                    VendorInvoice.total_amount == v.amount).first())
        if bill:
            continue
        out.append(LDraft("A-VEN-DOC-01", "accounting", "vendor_audit", "supporting_documents", "MISSING_DOCUMENTATION",
                          "MEDIUM", 0.7, f"Payment {v.voucher_number} to {names.get(vid, 'a vendor')} has no bill on record",
                          f"{v.voucher_number} pays {inr(v.amount)} to {names.get(vid, 'a vendor')} with no supplier bill "
                          "number and no matching vendor invoice in the books.", expected="A vendor invoice for every payment",
                          actual="No invoice / reference", recommended="Attach the vendor's bill (record it as a vendor "
                          "invoice) or record its number as the voucher reference.",
                          evidence={"voucher": v.voucher_number, "amount": str(money(v.amount))}, subject=str(v.id),
                          voucher_id=v.id, transaction_ref=v.voucher_number, voucher_date=v.voucher_date, vendor_id=vid))
    return out


def _vendor_paid(s: Scan, vendor_id, start: date, end: date) -> Decimal:
    rows = (s.db.query(Voucher.amount).filter(Voucher.society_id == s.sid, Voucher.vendor_id == vendor_id,
                                              Voucher.voucher_type == "payment", Voucher.is_cancelled == False,  # noqa: E712
                                              Voucher.voucher_date.between(start, end)).all())
    return sum((money(a) for (a,) in rows), D0)


def chk_resolution_amounts(s: Scan) -> List[LDraft]:
    """Payments to a vendor against what the society's resolutions approved for that vendor (all live resolutions
    together, so a later additional approval is taken into account)."""
    from app.modules.vendor.models.vendor import Vendor
    out = []
    rows = (s.db.query(SocietyResolution).filter(SocietyResolution.society_id == s.sid,
                                                 SocietyResolution.status.in_(resolutions.LIVE),
                                                 SocietyResolution.vendor_id.isnot(None),
                                                 SocietyResolution.approved_amount.isnot(None),
                                                 SocietyResolution.category.in_(("expense", "contract"))).all())
    by_vendor = defaultdict(list)
    for r in rows:
        if not resolutions.problems(r):
            by_vendor[r.vendor_id].append(r)
    names = {v.id: v.company_name for v in s.db.query(Vendor).filter(Vendor.society_id == s.sid)}
    for vid, rs in by_vendor.items():
        start = min(r.period_from or r.meeting_date for r in rs)
        end = max((r.period_to or s.today) for r in rs)
        approved = sum((money(r.approved_amount) for r in rs), D0)
        paid = _vendor_paid(s, vid, start, min(end, s.today))
        if paid <= approved:
            continue
        verified = all(r.status == "VERIFIED" for r in rs)
        out.append(LDraft("L-EXP-RES-01", "legal", "expenditure_approval", "resolution_comparison",
                          "POTENTIAL_NON_COMPLIANCE", "HIGH", 0.75 if verified else 0.55,
                          f"Payments to {names.get(vid, 'a vendor')} exceed the approved amount by {inr(paid - approved)}",
                          f"Resolution(s) {', '.join(r.resolution_number for r in rs)} approved {inr(approved)} for "
                          f"{names.get(vid, 'this vendor')} ({start} to {end}). Payments recorded in that period total "
                          f"{inr(paid)}. No further approval for the difference was found in the resolution register."
                          + ("" if verified else " Some of these resolutions are recorded but not yet verified."),
                          expected=f"≤ {inr(approved)}", actual=inr(paid),
                          recommended="Check whether an additional approval exists (record it in Resolutions) or whether "
                                      "the excess needs the committee's / General Body's ratification.",
                          evidence={"approved": str(approved), "paid": str(paid), "difference": str(paid - approved),
                                    "resolutions": [resolutions.resolution_dict(r) for r in rs],
                                    "calculation": f"{paid} − {approved} = {paid - approved}"},
                          subject=str(vid), vendor_id=vid))
    return out


@dataclass
class Threshold:
    """A figure used to test a transaction, with where it came from. It is never stated as more certain than its source."""
    amount: Optional[Decimal]
    label: str                        # how the figure is described to the user
    basis: str                        # STATUTE | SOCIETY_RULE | SOCIETY_SETTING | MODEL_REFERENCE | NONE
    source_rule: Optional[object]     # the LegalRule the figure comes from (None for a society setting)
    members: int
    governing: registry.Applicable    # what the registry says governs the topic


def _slab(rule, members: int) -> Optional[Decimal]:
    calc = rule.calculation_method or {}
    slabs = calc.get("slabs")
    if slabs:
        for upto, amount in slabs:
            if upto is None or members <= upto:
                return money(amount)
    if calc.get("value") is not None and calc.get("type") in ("max_amount", "reference_amount", "membership_slab_limit"):
        return money(calc["value"])
    return None


def committee_threshold(s: Scan, on: date) -> Threshold:
    """The committee's spending threshold, resolved through the legal source registry (D-03 of the functional audit).

    Order: a statutory rule whose figure is loaded → the society's own registered bye-law / resolution / policy in the
    registry → the limit the society set explicitly in Procurement settings (a society setting, not a legal source) →
    the model bye-law 157 reference (MODEL_REFERENCE: binding only if the registered bye-laws adopted it unchanged).
    The figure is always labelled with its source and status; it is never presented as a binding legal limit unless
    it comes from a verified binding source."""
    from app.modules.vendor.services.work_orders import procurement_limits
    app = s.rule("expenditure.committee_limit", on)
    limits = procurement_limits(s.db, s.sid)
    members = int(limits["members"])
    cands = app.candidates
    for r in cands:
        if r.source_level in registry.STATUTORY and _slab(r, members) is not None:
            verified = r.verification_status in registry.VERIFIED
            return Threshold(_slab(r, members), f"the limit under {r.rule_code} for {members} members"
                             + ("" if verified else " (statutory source not yet verified)"), "STATUTE", r, members, app)
    for r in cands:
        if r.source_level in registry.SOCIETY_LEVELS and _slab(r, members) is not None:
            return Threshold(_slab(r, members), f"the limit in your {registry.LEVEL_NAMES[r.source_level]} ({r.rule_code})"
                             + ("" if r.verification_status in registry.VERIFIED else ", not yet verified"),
                             "SOCIETY_RULE", r, members, app)
    if limits.get("committee_limit_set"):
        return Threshold(money(limits["committee_limit"]), "the committee limit entered in the society's Procurement "
                         "settings (a society setting, not a verified legal source)", "SOCIETY_SETTING", None, members, app)
    for r in cands:
        if r.source_level == "H" and _slab(r, members) is not None:
            return Threshold(_slab(r, members), f"the model bye-law {(r.bye_law_number or '157').replace('(model)', '').strip()} reference figure for "
                             f"{members} members — a MODEL figure, binding only if your registered bye-laws adopted it "
                             "unchanged, and not verified", "MODEL_REFERENCE", r, members, app)
    return Threshold(None, "no committee limit is loaded", "NONE", None, members, app)


def threshold_draft(s: Scan, th: Threshold, code, category, ccat, title, explanation, **kw) -> LDraft:
    """A finding judged against a Threshold: classified by the strength of the FIGURE's source (a model or unverified
    figure can never give more than a potential issue), citing both that source and the governing statutory rule."""
    gov = th.governing
    statutory_note = ""
    if gov.rule is not None and gov.rule.source_level in registry.STATUTORY and th.basis != "STATUTE":
        statutory_note = (f" The statutory limit ({gov.rule.rule_code}) is not loaded"
                          + (" and is under legal review" if gov.blocked else "") + ".")
    ev = {**kw.pop("evidence", {}), "threshold": str(th.amount) if th.amount is not None else None,
          "threshold_basis": th.basis, "threshold_source": th.label, "members_counted": th.members,
          "governing_rule": gov.rule.rule_code if gov.rule else None}
    if th.source_rule is None:                     # a society setting: an internal-policy deviation at most
        return LDraft(code, "legal", category, ccat, "INTERNAL_POLICY_DEVIATION", "MEDIUM", 0.6, title,
                      explanation + statutory_note, legal_rule_code=gov.rule.rule_code if gov.rule else None,
                      legal_source=registry.source_ref(gov.rule, gov), evidence=ev, **kw)
    app = registry.Applicable(topic=gov.topic, on=gov.on, rule=th.source_rule, candidates=gov.candidates,
                              conflicts=gov.conflicts,
                              blocked_by=registry.blocking_reviews(s.db, s.sid, th.source_rule.rule_code))
    return s.legal(code, category, ccat, app, title, explanation + statutory_note, evidence=ev, **kw)


def chk_work_orders(s: Scan) -> List[LDraft]:
    """Work orders: payments beyond the sanctioned amount, and sanctions above the committee's limit without a General
    Body resolution."""
    from app.modules.vendor.models.vendor import (
        SanctionLevel, VendorInvoice, VendorPaymentTransaction, WorkOrder, WorkOrderStatus,
    )
    out = []
    th = committee_threshold(s, s.today)
    committee = th.amount
    for wo in s.db.query(WorkOrder).filter(WorkOrder.society_id == s.sid, WorkOrder.status != WorkOrderStatus.CANCELLED):
        paid = sum((money(a) for (a,) in s.db.query(VendorPaymentTransaction.amount)
                    .join(VendorInvoice, VendorInvoice.id == VendorPaymentTransaction.invoice_id)
                    .filter(VendorInvoice.work_order_id == wo.id, VendorPaymentTransaction.is_reversed == False)), D0)  # noqa: E712
        extra = resolutions.authorising(s.db, s.sid, on=s.today, work_order_id=wo.id, categories=("expense", "contract"))
        approved = money(wo.sanctioned_amount) + extra.approved_total if wo.sanctioned_amount is not None else None
        if approved is not None and paid > approved:
            out.append(LDraft("L-EXP-WO-01", "legal", "expenditure_approval", "resolution_comparison",
                              "POTENTIAL_NON_COMPLIANCE", "HIGH", 0.7,
                              f"Work order {wo.wo_number}: paid {inr(paid)} against {inr(approved)} sanctioned",
                              f"'{wo.title}' was sanctioned for {inr(wo.sanctioned_amount)}"
                              + (f" plus {inr(extra.approved_total)} by later resolution(s)" if extra.resolutions else "")
                              + f". Payments total {inr(paid)}.", expected=f"≤ {inr(approved)}", actual=inr(paid),
                              recommended="Record the additional approval if one exists; otherwise the excess needs "
                                          "ratification by the competent authority.",
                              evidence={"sanctioned": str(money(wo.sanctioned_amount)), "additional": str(extra.approved_total),
                                        "paid": str(paid)}, subject=str(wo.id), vendor_id=wo.vendor_id))
        amount = money(wo.sanctioned_amount or wo.estimated_cost)
        if committee is not None and amount > committee and wo.sanction_level != SanctionLevel.GENERAL_BODY \
                and not wo.gb_resolution_no:
            gb = resolutions.authorising(s.db, s.sid, on=s.today, work_order_id=wo.id, vendor_id=wo.vendor_id,
                                         authority="GENERAL_BODY")
            if gb.resolutions:
                continue
            out.append(threshold_draft(s, th, "L-EXP-WO-02", "expenditure", "expenditure_approval",
                                       f"Work order {wo.wo_number} ({inr(amount)}) is above the committee threshold "
                                       "without a General Body resolution",
                                       f"'{wo.title}' is for {inr(amount)}, above {inr(committee)} — {th.label}. "
                                       "No General Body resolution is recorded for it.",
                                       expected="General Body approval above the committee threshold",
                                       actual="Committee / none",
                                       recommended="Record the General Body resolution (number and date) on the work "
                                                   "order, or place it before the General Body. Check the limit in "
                                                   "your registered bye-laws.",
                                       evidence={"amount": str(amount)}, subject=str(wo.id), vendor_id=wo.vendor_id))
    return out


def chk_repair_payments(s: Scan) -> List[LDraft]:
    """A one-time repair payment above the committee's limit with no work order or resolution behind it, and the
    financial year's cumulative repair spend."""
    out = []
    th = committee_threshold(s, s.today)
    committee = th.amount
    if committee is None:
        return out
    repair_ids = {s.accounts[k].id for k in REPAIR_KEYS if k in s.accounts}
    if not repair_ids:
        return out
    fy_start, _ = fiscal_year_bounds(fiscal_year(s.today))
    cumulative = D0
    for v in s.vouchers(min(fy_start, s.today - timedelta(days=365)), ("payment", "journal", "purchase")):
        amt = sum((money(e.debit) for e in v.entries if e.account_id in repair_ids), D0)
        if not amt:
            continue
        if v.voucher_date >= fy_start:
            cumulative += amt
        if v.source_type in ("vendor_invoice", "vendor_payment"):
            continue
        ok = resolutions.authorising(s.db, s.sid, on=v.voucher_date, vendor_id=v.vendor_id,
                                     account_id=next(iter(e.account_id for e in v.entries if e.account_id in repair_ids)),
                                     authority="GENERAL_BODY")
        if ok.resolutions and ok.approved_total >= amt:
            continue
        vth = committee_threshold(s, v.voucher_date)
        if vth.amount is None or amt <= vth.amount:
            continue
        out.append(threshold_draft(s, vth, "L-EXP-REP-01", "expenditure", "expenditure_approval",
                                   f"Repair expense {v.voucher_number} ({inr(amt)}) is above the committee threshold "
                                   "with no approval on record",
                                   f"{v.voucher_number} books {inr(amt)} of repairs in one payment, above {inr(vth.amount)} "
                                   f"— {vth.label}. No work order or General Body resolution covering it was found.",
                                   expected="General Body approval above the committee threshold",
                                   actual="No resolution found",
                                   recommended="Record the resolution that approved this work, or obtain ratification. "
                                               "Check the limit in your registered bye-laws.",
                                   evidence={"amount": str(amt)}, subject=str(v.id), voucher_id=v.id,
                                   transaction_ref=v.voucher_number, voucher_date=v.voucher_date, vendor_id=v.vendor_id))
    if cumulative > committee * 4:
        out.append(LDraft("L-EXP-REP-02", "legal", "expenditure", "expenditure_approval", "ADVISORY_OBSERVATION", "LOW", 0.4,
                          f"Repairs this financial year total {inr(cumulative)}",
                          f"Cumulative repair spending this year is {inr(cumulative)}, more than four times {inr(committee)} "
                          f"({th.label}). Rule 106C-13 also measures cumulative expenditure; its slabs are pending "
                          "verification.", recommended="Check the budget approved by the General Body.",
                          evidence={"cumulative": str(cumulative), "threshold": str(committee),
                                    "threshold_basis": th.basis}, subject=fiscal_year(s.today)))
    return out


def chk_vendor_concentration(s: Scan) -> List[LDraft]:
    from app.modules.vendor.models.vendor import Vendor
    since = s.today - timedelta(days=92)
    spend = defaultdict(lambda: D0)
    for v in s.vouchers(since, ("payment",)):
        if v.vendor_id:
            spend[v.vendor_id] += money(v.amount)
    total = sum(spend.values(), D0)
    if total < Decimal("50000") or len(spend) < 2:
        return []
    vid, top = max(spend.items(), key=lambda kv: kv[1])
    share = top / total * 100
    if share < 60:
        return []
    name = s.db.query(Vendor.company_name).filter(Vendor.id == vid).scalar()
    return [LDraft("A-VEN-CON-01", "accounting", "vendor_audit", None, "ADVISORY_OBSERVATION", "LOW", 0.5,
                   f"{share:.0f}% of vendor payments in three months went to {name}",
                   f"{inr(top)} of {inr(total)} paid to vendors since {since} went to one vendor.",
                   recommended="Usually fine for a main contractor; confirm the contract and its approval.",
                   evidence={"vendor": name, "share_pct": f"{share:.1f}", "amount": str(top), "total": str(total)},
                   subject=str(vid), vendor_id=vid)]


# ── Funds (Rule 106C-11) and borrowing (106C-10) ───────────────────────────────────────────────────────────────────

def chk_fund_utilisation(s: Scan) -> List[LDraft]:
    out = []
    funds = {s.accounts[k].id: k for k in FUND_KEYS if k in s.accounts}
    if not funds:
        return out
    income_ids = {a.id for a in s.account_by_id.values() if a.group and a.group.nature == "income"} if s.account_by_id else set()
    for v in s.vouchers(s.today - timedelta(days=730)):
        if v.reversal_of_id:
            continue
        for e in v.entries:
            if e.account_id not in funds or not money(e.debit):
                continue
            key, amt = funds[e.account_id], money(e.debit)
            app = s.rule("funds.utilisation", v.voucher_date)
            spec = ((app.rule.calculation_method or {}).get("funds", {}) if app.rule else {}).get(key, {})
            authority = spec.get("authority")
            match = resolutions.authorising(s.db, s.sid, on=v.voucher_date, account_id=e.account_id,
                                            categories=("fund_utilisation", "fund_transfer"),
                                            authority="GENERAL_BODY" if authority == "GENERAL_BODY" else None)
            fund_name = s.account_by_id[e.account_id].name
            to_income = [x for x in v.entries if money(x.credit) and x.account_id in income_ids]
            if to_income:
                out.append(LDraft("A-FND-INC-01", "accounting", "fund_monitoring", "fund_utilisation",
                                  "SUSPECTED_ACCOUNTING_ANOMALY", "HIGH", 0.8,
                                  f"{fund_name} moved to income by {v.voucher_number}",
                                  f"{v.voucher_number} debits {fund_name} by {inr(amt)} and credits an income ledger. A "
                                  "designated fund is not ordinary income.", expected="Fund used for its purpose",
                                  actual="Transferred to income", recommended="Check the purpose; reverse the transfer if wrong.",
                                  evidence={"fund": fund_name, "amount": str(amt)}, subject=f"{v.id}:{key}",
                                  voucher_id=v.id, transaction_ref=v.voucher_number, voucher_date=v.voucher_date))
            if not match.resolutions:
                out.append(s.legal("L-FND-USE-01", "funds", "fund_utilisation", app,
                                   f"{fund_name} used ({inr(amt)}) with no resolution on record",
                                   f"{v.voucher_number} on {v.voucher_date} draws {inr(amt)} from {fund_name}. "
                                   f"Its purpose: {spec.get('purpose', 'as approved')}; approval needed: "
                                   f"{(authority or 'the competent authority').replace('_', ' ').lower()}. No matching "
                                   "resolution was found in the register.",
                                   expected=f"Resolution of the {(authority or 'competent authority').replace('_', ' ').lower()}",
                                   actual="No resolution", recommended="Record the resolution that approved this use of the fund "
                                   "(category fund utilisation, ledger = the fund) or refer it to the committee.",
                                   evidence={"fund": fund_name, "amount": str(amt), "required_authority": authority,
                                             "purpose": spec.get("purpose")},
                                   subject=f"{v.id}:{key}", voucher_id=v.id, transaction_ref=v.voucher_number,
                                   voucher_date=v.voucher_date))
            elif match.approved_total and amt > match.approved_total:
                out.append(s.legal("L-FND-USE-02", "funds", "fund_utilisation", app,
                                   f"{fund_name} use {inr(amt)} exceeds the {inr(match.approved_total)} approved",
                                   f"{v.voucher_number} draws {inr(amt)}; resolution(s) "
                                   f"{', '.join(r.resolution_number for r in match.resolutions)} approved {inr(match.approved_total)}.",
                                   expected=f"≤ {inr(match.approved_total)}", actual=inr(amt),
                                   evidence={"amount": str(amt), "approved": str(match.approved_total)},
                                   subject=f"{v.id}:{key}", voucher_id=v.id, transaction_ref=v.voucher_number,
                                   voucher_date=v.voucher_date))
    return out


def _balance(s: Scan, account: Account) -> Decimal:
    dr, cr = (s.db.query(func.coalesce(func.sum(VoucherEntry.debit), 0), func.coalesce(func.sum(VoucherEntry.credit), 0))
              .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
              .filter(VoucherEntry.account_id == account.id, Voucher.society_id == s.sid, Voucher.is_cancelled == False)  # noqa: E712
              .one())
    opening = money(account.opening_balance) * (1 if account.opening_type == "cr" else -1)
    return opening + money(cr) - money(dr)          # credit balance positive for a fund


def chk_fund_balances(s: Scan) -> List[LDraft]:
    out = []
    for k in FUND_KEYS:
        a = s.accounts.get(k)
        if not a:
            continue
        bal = _balance(s, a)
        if bal < 0:
            out.append(LDraft("A-FND-BAL-01", "accounting", "fund_monitoring", None, "SUSPECTED_ACCOUNTING_ANOMALY", "HIGH", 0.85,
                              f"{a.name} is overdrawn ({inr(-bal)} debit balance)",
                              f"{a.name} should carry a credit balance (money held for its purpose); it shows a debit "
                              f"balance of {inr(-bal)}: more has been used than was ever contributed.",
                              expected="Credit balance ≥ 0", actual=f"{inr(-bal)} Dr",
                              recommended="Review the fund's ledger for wrong postings or utilisation without contributions.",
                              evidence={"balance": str(bal)}, subject=k))
    return out


def chk_borrowing(s: Scan) -> List[LDraft]:
    out = []
    loans = s.accounts.get("loans")
    if not loans:
        return out
    for v in s.vouchers(s.today - timedelta(days=730)):
        amt = sum((money(e.credit) for e in v.entries if e.account_id == loans.id), D0)
        if not amt or v.reversal_of_id:
            continue
        app = s.rule("borrowing.authority", v.voucher_date)
        if resolutions.authorising(s.db, s.sid, on=v.voucher_date, account_id=loans.id, categories=("borrowing",),
                                   authority="GENERAL_BODY").resolutions:
            continue
        out.append(s.legal("L-BOR-01", "borrowing", "borrowing", app,
                           f"Borrowing of {inr(amt)} ({v.voucher_number}) without a General Body resolution on record",
                           f"{v.voucher_number} credits Loans with {inr(amt)}. Borrowing needs the General Body's approval; "
                           "none is recorded.", expected="General Body resolution", actual="None found",
                           recommended="Record the General Body resolution approving the loan.",
                           evidence={"amount": str(amt)}, subject=str(v.id), voucher_id=v.id,
                           transaction_ref=v.voucher_number, voucher_date=v.voucher_date))
    return out


def chk_transfer_premium(s: Scan) -> List[LDraft]:
    out = []
    acct = s.accounts.get("transfer_premium")
    if not acct:
        return out
    for v in s.vouchers(s.today - timedelta(days=730)):
        amt = sum((money(e.credit) for e in v.entries if e.account_id == acct.id), D0)
        if not amt:
            continue
        app = s.rule("transfer.premium.max_amount", v.voucher_date)
        cap = app.effective_value
        if cap is None or amt <= Decimal(str(cap)):
            continue
        flat = next((e.flat_id for e in v.entries if e.flat_id), None)
        out.append(s.legal("L-TRF-01", "transfer", "transfer_charges", app,
                           f"Transfer premium {inr(amt)} on {v.voucher_number} is above {inr(cap)}",
                           f"{v.voucher_number} records a transfer premium of {inr(amt)}. The figure on record for the "
                           f"ceiling is {inr(cap)} ({app.rule.rule_code}, not verified — check the current Government order "
                           "and the registered bye-laws).", expected=f"≤ {inr(cap)}", actual=inr(amt),
                           recommended="Check the applicable order and bye-law; refund the excess if confirmed.",
                           evidence={"amount": str(amt), "ceiling": cap}, subject=str(v.id), voucher_id=v.id,
                           transaction_ref=v.voucher_number, voucher_date=v.voucher_date, flat_id=flat))
    return out


# ── Budget (internal policy) ───────────────────────────────────────────────────────────────────────────────────────

def chk_budget(s: Scan) -> List[LDraft]:
    out = []
    fy = fiscal_year(s.today)
    start, end = fiscal_year_bounds(fy)
    for bl in s.db.query(BudgetLine).filter(BudgetLine.society_id == s.sid, BudgetLine.fiscal_year == fy):
        a = s.account_by_id.get(bl.account_id)
        if not a:
            continue
        dr, cr = (s.db.query(func.coalesce(func.sum(VoucherEntry.debit), 0), func.coalesce(func.sum(VoucherEntry.credit), 0))
                  .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                  .filter(VoucherEntry.account_id == a.id, Voucher.society_id == s.sid, Voucher.is_cancelled == False,  # noqa: E712
                          Voucher.voucher_type != "closing", Voucher.voucher_date.between(start, end)).one())
        actual, budget = money(dr) - money(cr), money(bl.approved_amount)
        if budget <= 0:
            continue
        if actual > budget:
            pct = (actual - budget) / budget * 100
            out.append(LDraft("G-BUD-01", "accounting", "budget", "budget", "INTERNAL_POLICY_DEVIATION",
                              "HIGH" if pct > 25 else "MEDIUM", 0.9,
                              f"{a.name}: spent {inr(actual)} against a budget of {inr(budget)} ({pct:.0f}% over)",
                              f"The approved {fy} budget for {a.name} is {inr(budget)}; spending so far is {inr(actual)}. "
                              "A budget overrun is an internal-policy deviation; it is not by itself an absence of legal "
                              "authority — the expenditure may still have been validly approved.",
                              expected=f"≤ {inr(budget)}", actual=inr(actual),
                              recommended="Place the overrun before the committee / General Body for approval, or revise "
                                          "the budget.", evidence={"budget": str(budget), "actual": str(actual),
                                                                   "fiscal_year": fy}, subject=f"{fy}:{a.id}"))
        else:
            elapsed = max((min(s.today, end) - start).days, 1) / 365
            if elapsed >= 0.25 and actual / Decimal(str(elapsed)) > budget * Decimal("1.15"):
                out.append(LDraft("G-BUD-02", "accounting", "budget", "budget", "ADVISORY_OBSERVATION", "LOW", 0.5,
                                  f"{a.name} is on course to exceed its budget",
                                  f"{inr(actual)} spent in {elapsed * 12:.0f} months against a full-year budget of {inr(budget)}.",
                                  evidence={"budget": str(budget), "actual": str(actual)}, subject=f"{fy}:{a.id}"))
    return out


# ── Legal sources, documents, calendar, recovery ───────────────────────────────────────────────────────────────────

def chk_legal_sources(s: Scan) -> List[LDraft]:
    out = []
    reviews = (s.db.query(LegalReview).filter(LegalReview.status.in_(OPEN_REVIEW_STATUSES), LegalReview.blocking == True,  # noqa: E712
                                              LegalReview.society_id.is_(None) | (LegalReview.society_id == s.sid)).all())
    for r in reviews:
        out.append(LDraft("L-SRC-CON-01", "legal", "legal_sources", "legal_source_conflict", "LEGAL_SOURCE_CONFLICT",
                          "MEDIUM", 0.9, r.title, r.description + " Rules affected cannot produce a confirmed violation "
                          "until a legal reviewer resolves this.", recommended="Assign to the society's legal advisor; "
                          "record the decision under Legal reviews.",
                          evidence={"review_id": str(r.id), "review_type": r.review_type, "rule_codes": r.rule_codes,
                                    "details": r.details}, subject=str(r.id)))
    prof = registry.profile_for(s.db, s.sid)
    bylaw = s.db.get(LegalDocument, prof.registered_bylaw_document_id) if prof and prof.registered_bylaw_document_id else None
    if not bylaw or bylaw.status not in OPERATIVE_DOCUMENT_STATUSES or bylaw.verification_status not in VERIFIED:
        out.append(LDraft("L-SRC-BYL-01", "legal", "legal_sources", "bye_laws", "MISSING_DOCUMENTATION", "MEDIUM", 0.95,
                          "The society's registered bye-laws are not on record and verified",
                          "Compliance checks currently rely on the jurisdiction rule pack and model bye-law references "
                          "only. The model bye-laws are not this society's registered bye-laws.",
                          recommended="Upload the registered bye-laws and approved amendments in the Legal Library and "
                                      "verify them.", subject="registered-bylaws"))
    return out


def chk_calendar(s: Scan) -> List[LDraft]:
    out = []
    for it in s.db.query(ComplianceItem).filter(ComplianceItem.society_id == s.sid, ComplianceItem.completion_status == "PENDING",
                                                ComplianceItem.due_date.isnot(None), ComplianceItem.due_date < s.today):
        if it.applicability == "NOT_APPLICABLE":
            continue
        applicable = it.applicability == "APPLICABLE"
        out.append(LDraft("L-CAL-01", "legal", "statutory_compliance", it.category.lower(),
                          "POTENTIAL_NON_COMPLIANCE" if applicable else "ADVISORY_OBSERVATION",
                          "HIGH" if applicable else "LOW", 0.6 if applicable else 0.3,
                          (f"{it.title} ({it.financial_period}) is overdue: due {it.due_date}, not marked done"
                           if applicable else
                           f"{it.title} ({it.financial_period}): confirm whether it applies (due {it.due_date})"),
                          f"{it.title}: due {it.due_date} ({it.due_date_basis or 'due date as configured'}). "
                          + ("" if applicable else "Applicability is not established: professional verification required. "),
                          recommended=f"Responsible: {it.responsible_role or 'committee'}. Mark it done with the evidence, "
                                      "or record why it does not apply.",
                          legal_rule_code=it.legal_rule_code,
                          evidence={"item": it.code, "period": it.financial_period, "legal_source": it.legal_source,
                                    "applicability": it.applicability}, subject=f"{it.code}:{it.financial_period}"))
    # Audit report for the last completed financial year.
    last_fy = fiscal_year(fiscal_year_bounds(fiscal_year(s.today))[0] - timedelta(days=1))
    _, last_end = fiscal_year_bounds(last_fy)
    start, basis = compliance_calendar.obligation_start(s.db, s.sid)
    before = bool(start and last_end < start)
    if s.today > date(last_end.year, 9, 30) and not (before and basis == "REGISTRATION"):
        has = (s.db.query(LegalDocument.id).filter(LegalDocument.society_id == s.sid, LegalDocument.document_type == "AUDIT_REPORT",
                                                   LegalDocument.status != "REJECTED",
                                                   (LegalDocument.issue_date.is_(None)) | (LegalDocument.issue_date > last_end))
               .first())
        if not has:
            if before:      # the year ended before the society joined the app and no registration date is known
                out.append(LDraft("L-AUD-01", "legal", "statutory_compliance", "statutory_audit", "ADVISORY_OBSERVATION",
                                  "LOW", 0.3, f"Audit report for {last_fy}: confirm whether it applies",
                                  f"{last_fy} ended before the society started using the app ({start:%d %b %Y}) and its "
                                  "registration date is not recorded, so the app cannot tell whether an audit was due. "
                                  "Upload the report if there is one, or record the registration date in the legal profile.",
                                  recommended="Upload the audit report, or record the society's registration date.",
                                  evidence={"obligation_start": start.isoformat(), "basis": basis}, subject=last_fy))
            else:
                out.append(LDraft("L-AUD-01", "legal", "statutory_compliance", "statutory_audit", "MISSING_DOCUMENTATION",
                                  "MEDIUM", 0.8, f"No statutory audit report for {last_fy} is on record",
                                  f"The {last_fy} audit report has not been uploaded to the Legal Library.",
                                  recommended="Upload the audit report (and the rectification report once filed).",
                                  subject=last_fy))
    return out


def chk_recovery(s: Scan) -> List[LDraft]:
    from app.modules.accounts_agent.legal import recovery
    rep = recovery.arrears(s.db, s.sid, s.today)
    defaulters = [r for r in rep["flats"] if r["defaulter"]]
    if not defaulters:
        return []
    out = [LDraft("L-REC-01", "legal", "recovery", "member_arrears", "ADVISORY_OBSERVATION", "MEDIUM", 0.8,
                  f"{len(defaulters)} member(s) have dues unpaid for more than {rep['defaulter_after_months']} months",
                  f"{inr(sum(Decimal(r['outstanding']) for r in defaulters))} is overdue beyond "
                  f"{rep['defaulter_after_months']} months. See Recovery for the flat-wise ageing and the readiness "
                  "checklist. The agent never issues notices or starts recovery.",
                  recommended="Review the defaulters; the committee decides on reminders or recovery action.",
                  evidence={"flats": [{"flat": r["flat"], "outstanding": r["outstanding"], "oldest_due": r["oldest_due"]}
                                      for r in defaulters[:50]]},
                  subject="defaulters", legal_rule_code=rep["rule"]["rule_code"] if rep["rule"] else None,
                  legal_source=rep["rule"])]
    if not s.db.query(SocietyResolution.id).filter(SocietyResolution.society_id == s.sid, SocietyResolution.category == "recovery",
                                                   SocietyResolution.status.in_(resolutions.LIVE)).first():
        out.append(LDraft("L-REC-02", "legal", "recovery", "recovery_documentation", "MISSING_DOCUMENTATION", "LOW", 0.6,
                          "No committee resolution on recovery of dues is on record",
                          "There are defaulters but no resolution authorising recovery proceedings is in the register. "
                          "A recovery application would need one.", recommended="Only if the committee decides to "
                          "proceed: record its resolution (category: recovery).", subject="recovery-resolution"))
    return out


CHECKS = [chk_interest_setting, chk_non_occupancy_setting, chk_non_occupancy_bills, chk_charge_apportionment,
          chk_fund_rates, chk_bill_integrity, chk_bill_allocation, chk_bill_interest, chk_duplicate_receipts,
          chk_vendor_invoices, chk_resolution_amounts, chk_work_orders, chk_repair_payments, chk_vendor_concentration,
          chk_fund_utilisation, chk_fund_balances, chk_borrowing, chk_transfer_premium, chk_budget, chk_legal_sources,
          chk_calendar, chk_recovery]


def _residential():
    from app.modules.accounts_agent.legal.ledger_mapping import CHECKS as LEDGER
    from app.modules.accounts_agent.legal.residential_checks import CHECKS as RESIDENTIAL
    return RESIDENTIAL + LEDGER


def run_scan(db: Session, society_id: UUID, actor_id: Optional[UUID] = None) -> dict:
    """Run every check for ONE society and store the results. Caller commits."""
    registry.ensure_jurisdiction_pack(db)
    s = Scan(db, society_id)
    compliance_calendar.ensure_items(db, society_id, s.today)
    registry.detect_conflicts(db, society_id, s.today)
    drafts: List[LDraft] = []
    failed: List[str] = []
    for fn in CHECKS + _residential():
        try:
            with db.begin_nested():
                drafts += fn(s)
        except Exception:  # noqa: BLE001 — one failing check never stops the others
            logger.exception("[accounts-agent] compliance check %s failed society=%s", fn.__name__, society_id)
            failed.append(fn.__name__)
    created, live = store(db, society_id, drafts)
    resolved = auto_resolve(db, society_id, live)
    summary = {"checks": len(CHECKS) + len(_residential()), "failed_checks": failed, "detected": len(drafts), "new_findings": len(created),
               "auto_resolved": resolved, "scanned_at": datetime.utcnow().isoformat()}
    audit.record(db, society_id, "compliance_scan", "society", society_id, actor_id,
                 {k: v for k, v in summary.items() if k != "scanned_at"})
    return {**summary, "new_finding_ids": [str(f.id) for f in created], "_created": created}


def store(db: Session, society_id: UUID, drafts: List[LDraft]):
    created, live = [], set()
    existing = {f.dedupe_key: f for f in db.query(AgentFinding).filter(AgentFinding.society_id == society_id,
                                                                        AgentFinding.dedupe_key.like(f"{PREFIX}%"))}
    for d in drafts:
        if d.key in live:
            continue
        live.add(d.key)
        f = existing.get(d.key)
        if f is not None:
            if f.status in ("NEW", "UNDER_REVIEW"):
                f.explanation, f.evidence, f.severity, f.finding_class = d.explanation, d.evidence, d.severity, d.finding_class
                f.legal_source, f.actual_behaviour = d.legal_source, d.actual
            elif f.status == "RESOLVED" and (f.resolution_note or "").startswith("No longer detected"):
                f.status, f.resolved_at, f.resolution_note = "NEW", None, None
                f.explanation, f.evidence = d.explanation, d.evidence
                audit.record(db, society_id, "finding_reopened", "finding", f.id, details={"rule": d.rule_code})
            continue
        f = AgentFinding(society_id=society_id, voucher_id=d.voucher_id, transaction_ref=d.transaction_ref,
                         voucher_date=d.voucher_date, category=d.category, finding_class=d.finding_class,
                         severity=d.severity, confidence=d.confidence, rule_code=d.rule_code, dedupe_key=d.key,
                         title=d.title[:200], explanation=d.explanation, expected_behaviour=d.expected,
                         actual_behaviour=d.actual, evidence=d.evidence, recommended_action=d.recommended, status="NEW",
                         engine=d.engine, compliance_category=d.compliance_category, legal_rule_code=d.legal_rule_code,
                         legal_source=d.legal_source, flat_id=d.flat_id, vendor_id=d.vendor_id)
        db.add(f)
        db.flush()
        audit.record(db, society_id, "finding_created", "finding", f.id,
                     details={"rule": d.rule_code, "severity": d.severity, "class": d.finding_class})
        created.append(f)
    return created, live


def auto_resolve(db: Session, society_id: UUID, live: set) -> int:
    n = 0
    for f in db.query(AgentFinding).filter(AgentFinding.society_id == society_id, AgentFinding.dedupe_key.like(f"{PREFIX}%"),
                                           AgentFinding.status.in_(("NEW", "UNDER_REVIEW"))):
        if f.dedupe_key not in live:
            f.status, f.resolved_at = "RESOLVED", datetime.utcnow()
            f.resolution_note = "No longer detected by the compliance scan"
            audit.record(db, society_id, "finding_auto_resolved", "finding", f.id, details={"reason": "scan"})
            n += 1
    return n
