"""TDS on vendor payments: who the vendor is decides the rate, and it is worked out when we pay.

A vendor is set up once in the master with a **constitution** (individual / proprietor, HUF, partnership firm, LLP,
private or public company, AOP, trust...) and the usual **section** of payment (a contract under 194C, professional
fees under 194J...). When a bill is paid, `compute_payment_tds` looks up the rule for that section and kind of payee,
applies the yearly and single-payment limits, a missing PAN (20%) or a lower-deduction certificate, and returns the TDS
to take off. VendorService.record_vendor_payment saves it on the payment and the posting engine books the entry:
Dr Sundry creditors (the amount settled), Cr Bank (what the vendor receives), Cr TDS payable (what we owe the
government).

The rates, limits and who they apply to are data (accounting_tax_configurations, one row per section and kind of
payee, with effective dates) so they can be corrected when the law changes. `DEFAULT_RULES` are what a society starts
with; they are filled in on first use and never overwrite a row the society has edited. They are defaults to be
confirmed with the society's chartered accountant, not tax advice.
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.models.taxes import TaxConfiguration
from app.modules.vendor.models.vendor import Vendor, VendorCategory, VendorPaymentTransaction

NO_PAN_RATE = Decimal("20")            # section 206AA: no PAN, deduct at 20% or the normal rate, whichever is higher
RULES_EFFECTIVE_FROM = date(2025, 4, 1)

PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")

# value, label, kind of payee for the rate, the letters a PAN of this kind has as its 4th character
CONSTITUTIONS: List[Tuple[str, str, str, Tuple[str, ...]]] = [
    ("individual_proprietor", "Individual / Proprietorship (self business)", "individual_huf", ("P",)),
    ("huf", "HUF (Hindu Undivided Family)", "individual_huf", ("H",)),
    ("partnership_firm", "Partnership firm", "other", ("F",)),
    ("llp", "LLP / LLC (limited liability partnership)", "other", ("F",)),
    ("private_limited", "Private Limited company", "other", ("C",)),
    ("public_limited", "Public Limited company", "other", ("C",)),
    ("aop_boi", "AOP / BOI (association of persons)", "other", ("A", "B")),
    ("cooperative_society", "Co-operative society", "other", ("A",)),
    ("trust", "Trust", "other", ("T",)),
    ("government", "Government / local authority", "other", ("G", "L", "J")),
    ("other", "Other", "other", ()),
]
CONSTITUTION_VALUES = {c[0] for c in CONSTITUTIONS}
_PAYEE_CLASS = {c[0]: c[2] for c in CONSTITUTIONS}
_PAN_LETTERS = {c[0]: c[3] for c in CONSTITUTIONS}
_PAN_KIND = {"P": "an individual", "H": "a HUF", "C": "a company", "F": "a firm or LLP", "A": "an association (AOP)",
             "B": "a body of individuals", "T": "a trust", "G": "the government", "L": "a local authority",
             "J": "an artificial juridical person"}

# value, label, short label. The value is stored on the vendor and on each payment.
SECTIONS: List[Tuple[str, str, str]] = [
    ("194C", "Contract / work: security, housekeeping, repairs, AMC (194C)", "194C contract"),
    ("194J_PROF", "Professional fees: CA, architect, lawyer, doctor (194J)", "194J professional"),
    ("194J_TECH", "Technical services / IT support (194J)", "194J technical"),
    ("194I_PM", "Rent of plant and machinery (194I)", "194I rent: machinery"),
    ("194I_LB", "Rent of land, building or furniture (194I)", "194I rent: property"),
    ("194H", "Commission or brokerage (194H)", "194H commission"),
]
SECTION_VALUES = {s[0] for s in SECTIONS}
SECTION_LABELS = {s[0]: s[2] for s in SECTIONS}

# What a vendor of each kind is usually paid under, to start the form off. The person can change it.
CATEGORY_DEFAULT_SECTION: Dict[str, Optional[str]] = {
    VendorCategory.ELECTRICAL.value: "194C", VendorCategory.PLUMBING.value: "194C", VendorCategory.LIFT.value: "194C",
    VendorCategory.SECURITY.value: "194C", VendorCategory.HOUSEKEEPING.value: "194C",
    VendorCategory.GARDENING.value: "194C", VendorCategory.PEST_CONTROL.value: "194C",
    VendorCategory.CCTV.value: "194C", VendorCategory.WATER_SUPPLY.value: "194C",
    VendorCategory.GENERATOR.value: "194C", VendorCategory.CIVIL.value: "194C",
    VendorCategory.IT.value: "194J_TECH", VendorCategory.OTHER.value: None,
}

# section, payee class, rate %, yearly limit, single-payment limit, name
DEFAULT_RULES: List[Tuple[str, str, str, Optional[str], Optional[str], str]] = [
    ("194C", "individual_huf", "1", "100000", "30000", "Contract: individual / HUF"),
    ("194C", "other", "2", "100000", "30000", "Contract: firm, LLP, company, other"),
    ("194J_PROF", "any", "10", "50000", None, "Professional fees"),
    ("194J_TECH", "any", "2", "50000", None, "Technical services"),
    ("194I_PM", "any", "2", "600000", None, "Rent: plant and machinery"),
    ("194I_LB", "any", "10", "600000", None, "Rent: land, building, furniture"),
    ("194H", "any", "2", "20000", None, "Commission / brokerage"),
]


def rule_code(section: str, payee_class: str) -> str:
    return f"TDS-{section}-{payee_class}"


def payee_class(constitution: Optional[str]) -> Optional[str]:
    return _PAYEE_CLASS.get(constitution or "")


def constitution_label(value: Optional[str]) -> Optional[str]:
    return next((c[1] for c in CONSTITUTIONS if c[0] == value), None)


def options() -> dict:
    return {
        "constitutions": [{"value": c[0], "label": c[1]} for c in CONSTITUTIONS],
        "sections": [{"value": s[0], "label": s[1], "short": s[2]} for s in SECTIONS],
        "category_default_section": CATEGORY_DEFAULT_SECTION,
        "no_pan_rate": str(NO_PAN_RATE),
    }


def pan_mismatch(pan: Optional[str], constitution: Optional[str]) -> Optional[str]:
    """A PAN's 4th letter says what kind of holder it is. A vendor entered as a company with an individual's PAN would
    be deducted at the wrong rate, so say so (None when it agrees, or when either is missing)."""
    if not pan or not constitution or not PAN_RE.match(pan):
        return None
    letters = _PAN_LETTERS.get(constitution) or ()
    if not letters or pan[3] in letters:
        return None
    return (f"This PAN belongs to {_PAN_KIND.get(pan[3], 'another kind of holder')}, but the vendor is entered as "
            f"{constitution_label(constitution)}. Correct the type or the PAN: the TDS rate depends on it.")


def ensure_default_rules(db: Session, society_id) -> None:
    """Fill in the society's TDS rules the first time they are needed. Rows already there (edited or not) are left alone."""
    have = {c for (c,) in db.query(TaxConfiguration.code).filter(
        TaxConfiguration.society_id == society_id, TaxConfiguration.tax_type == "TDS")}
    added = False
    for section, klass, rate, yearly, single, name in DEFAULT_RULES:
        code = rule_code(section, klass)
        if code in have:
            continue
        db.add(TaxConfiguration(
            society_id=society_id, code=code, name=name, tax_type="TDS", rate=Decimal(rate), section_code=section,
            payee_class=klass, base_type="taxable_amount", threshold_amount=Decimal(yearly) if yearly else None,
            single_threshold=Decimal(single) if single else None, effective_from=RULES_EFFECTIVE_FROM,
            ledger_system_key="tds_payable", is_active=True,
            notes="Starting rule, confirm with the society's chartered accountant"))
        added = True
    if added:
        db.flush()


def find_rule(db: Session, society_id, section: str, klass: str, on: date) -> Optional[TaxConfiguration]:
    rows = db.query(TaxConfiguration).filter(
        TaxConfiguration.society_id == society_id, TaxConfiguration.tax_type == "TDS",
        TaxConfiguration.section_code == section, TaxConfiguration.is_active == True,  # noqa: E712
        TaxConfiguration.payee_class.in_([klass, "any"]),
        TaxConfiguration.effective_from <= on,
        (TaxConfiguration.effective_to.is_(None) | (TaxConfiguration.effective_to >= on)),
    ).order_by(TaxConfiguration.effective_from.desc()).all()
    exact = [r for r in rows if r.payee_class == klass]
    return (exact or rows or [None])[0]


def financial_year(on: date) -> Tuple[date, date]:
    start = date(on.year if on.month >= 4 else on.year - 1, 4, 1)
    return start, date(start.year + 1, 3, 31)


def _d(v) -> Decimal:
    return Decimal(v or 0)


def _money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rupees(v: Decimal) -> Decimal:
    """TDS is rounded to the nearest rupee."""
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))


def _inr(v: Decimal) -> str:
    v = int(v)
    s = str(abs(v))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return "₹" + s


@dataclass
class TdsResult:
    applies: bool
    section: Optional[str]
    rate: Decimal
    taxable_value: Decimal
    base: Decimal
    tds: Decimal
    note: str
    rule_code: Optional[str] = None

    @property
    def section_label(self) -> Optional[str]:
        return SECTION_LABELS.get(self.section or "")


def _none(section, taxable, note, rule_code=None) -> TdsResult:
    """No TDS this time. `rule_code` is set when a rule governed the payment (it was under the limit), so the payment
    still counts towards the year's total for that section."""
    return TdsResult(False, section, Decimal("0"), taxable, Decimal("0.00"), Decimal("0.00"), note, rule_code)


def compute_payment_tds(db: Session, vendor: Vendor, inv, amount, paid_date: date) -> TdsResult:
    """The TDS to deduct from paying `amount` against `inv` on `paid_date`. Reads, never writes (apart from filling in
    the society's default rules the first time). `amount` is what is settled against the bill, GST included."""
    amount = _d(amount)
    total = _d(inv.total_amount)
    taxable = _money(amount * _d(inv.amount) / total) if total > 0 else _money(amount)   # TDS is on the value without GST
    section = vendor.tds_section
    if _d(inv.tds_amount) > 0:
        return _none(inv.tds_section or section, taxable, "TDS was already deducted when this bill was booked")
    if not section:
        return _none(None, taxable, "")
    if section not in SECTION_VALUES:
        return _none(section, taxable, f"Section {section} is not one the app knows. Correct the vendor's TDS section")
    klass = payee_class(vendor.constitution)
    if klass is None:
        return _none(section, taxable, "Set the vendor's type (individual, firm, company...) so the TDS rate can be worked out")

    ensure_default_rules(db, vendor.society_id)
    rule = find_rule(db, vendor.society_id, section, klass, paid_date)
    if rule is None:
        return _none(section, taxable, f"No TDS rate is set for {SECTION_LABELS[section]} on {paid_date:%d %b %Y}")

    fy_start, fy_end = financial_year(paid_date)
    before_value, before_base = db.query(
        func.coalesce(func.sum(VendorPaymentTransaction.taxable_value), 0),
        func.coalesce(func.sum(VendorPaymentTransaction.tds_base_amount), 0),
    ).filter(
        VendorPaymentTransaction.vendor_id == vendor.id, VendorPaymentTransaction.tds_section == section,
        VendorPaymentTransaction.is_reversed == False,  # noqa: E712
        VendorPaymentTransaction.payment_date >= fy_start, VendorPaymentTransaction.payment_date <= fy_end,
    ).one()
    before_value, before_base = _d(before_value), _d(before_base)
    after_value = before_value + taxable

    yearly, single = rule.threshold_amount, rule.single_threshold
    over_yearly = yearly is not None and after_value > _d(yearly)
    over_single = single is not None and taxable > _d(single)
    if (yearly is not None or single is not None) and not (over_yearly or over_single):
        limits = []
        if yearly is not None:
            limits.append(f"the {_inr(_d(yearly))} limit for the year ({_inr(after_value)} paid so far)")
        if single is not None:
            limits.append(f"{_inr(_d(single))} in one payment")
        return _none(section, taxable, f"No TDS: under {' and '.join(limits)}", rule.code)
    # Crossing the yearly limit brings in everything paid so far that was not taxed; a single payment over its own
    # limit is taxed on its own.
    base = _money(after_value - before_base) if over_yearly else taxable

    rate, why = _d(rule.rate), []
    lower = vendor.tds_lower_rate
    if (lower is not None and (vendor.tds_lower_valid_from is None or vendor.tds_lower_valid_from <= paid_date)
            and (vendor.tds_lower_valid_to is None or vendor.tds_lower_valid_to >= paid_date)):
        rate = _d(lower)
        cert = f" {vendor.tds_lower_cert_no}" if vendor.tds_lower_cert_no else ""
        why.append(f"lower-deduction certificate{cert}")
    elif not vendor.pan_number:
        if NO_PAN_RATE > rate:
            rate = NO_PAN_RATE
        why.append("no PAN on file, so 20%")
    tds = min(_rupees(base * rate / Decimal("100")), _money(amount))
    note = f"{SECTION_LABELS[section]} at {rate.normalize():f}% on {_inr(base)}"
    if why:
        note += f" ({'; '.join(why)})"
    if over_yearly and base > taxable:
        note += f". Includes {_inr(base - taxable)} paid earlier this year before the limit was crossed"
    return TdsResult(tds > 0, section, rate, taxable, base, tds, note, rule.code)
