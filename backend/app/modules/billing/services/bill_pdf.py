"""A4 PDF for a MaintenanceBill, in the layout housing societies in
Mumbai commonly send (Maharashtra model bye-laws: charges under the heads of
bye-laws 65-67, arrears and interest on arrears shown on the bill):

- a grey letterhead band (society name, Regn. No., address, GSTIN/PAN) over
  a red rule, then "Maintenance Bill";
- a box with the member's name, flat, area, mobile and e-mail on the left,
  and bill no., bill date, due date and bill period on the right;
- the heads table (No / Head / Amount). The society's monthly running
  expenses (service charges, water, common electricity, lift, security,
  housekeeping, insurance, …) are shown together as one head, "Maintenance
  Charges"; the funds and levies the bye-laws keep separate have their own
  heads (Sinking Fund, Repair & Maintenance Fund, Property Tax, Non
  Occupancy, Parking, Cheque Bounce, In & Out, Other) and print 0.00 when
  not charged;
- Current Bill Amount, Arrears/Advances, Current Interest/Late Fees,
  Previous Interest/Late Fees and the Total Maintenance Payable Amount;
- Notes: how to pay by NEFT (beneficiary, account, IFSC, bank), interest on
  late payment, queries within 7 days, dues subject to audit, the society's
  own notes;
- "This is a Computer Generated bill, hence no signature is required.";
- the receipts received towards the flat's previous bill, as a short table
  (each payment's receipt itself is a separate document — receipt_pdf).

Amounts print as "Rs." — the standard PDF fonts have no rupee glyph.
"""
import json
import re
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from xml.sax.saxutils import escape

from app.modules.billing.models.billing import (
    ChargeType, MaintenanceBill, MaintenanceSettings, PaymentMode, ReconciliationStatus,
)

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#555555")
FRAME = colors.HexColor("#8A8A8A")
RULE = colors.HexColor("#9CA3AF")
BAND = colors.HexColor("#D9D9D9")
RED = colors.HexColor("#C0474B")
ACCENT = colors.HexColor("#0B4A8B")
ZERO = Decimal("0")

_base = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=11.5, textColor=INK)
S = {
    "society": ParagraphStyle("society", parent=_base, fontName="Helvetica-Bold", fontSize=15, leading=19,
                              alignment=TA_CENTER),
    "centre": ParagraphStyle("centre", parent=_base, fontSize=9, leading=11.5, alignment=TA_CENTER),
    "centre_small": ParagraphStyle("centre_small", parent=_base, fontSize=8, alignment=TA_CENTER, textColor=MUTED),
    "title": ParagraphStyle("title", parent=_base, fontName="Helvetica-Bold", fontSize=13, leading=16,
                            alignment=TA_CENTER),
    "cell": _base,
    "cell_b": ParagraphStyle("cell_b", parent=_base, fontName="Helvetica-Bold"),
    "cell_r": ParagraphStyle("cell_r", parent=_base, alignment=TA_RIGHT),
    "cell_rb": ParagraphStyle("cell_rb", parent=_base, fontName="Helvetica-Bold", alignment=TA_RIGHT),
    "cell_c": ParagraphStyle("cell_c", parent=_base, alignment=TA_CENTER),
    "cell_cb": ParagraphStyle("cell_cb", parent=_base, fontName="Helvetica-Bold", alignment=TA_CENTER),
    "tab": ParagraphStyle("tab", parent=_base, fontSize=11, leading=13, alignment=TA_CENTER),
    "note": ParagraphStyle("note", parent=_base, fontSize=8.8, leading=12),
    "small": ParagraphStyle("small", parent=_base, fontSize=7.5, leading=9.5, textColor=MUTED),
    "small_r": ParagraphStyle("small_r", parent=_base, fontSize=7.5, leading=9.5, alignment=TA_RIGHT),
    "sign": ParagraphStyle("sign", parent=_base, fontSize=8, alignment=TA_CENTER),
    "foot": ParagraphStyle("foot", parent=_base, fontSize=8, alignment=TA_CENTER),
    "rc": ParagraphStyle("rc", parent=_base, fontSize=8, leading=10),
    "rc_b": ParagraphStyle("rc_b", parent=_base, fontName="Helvetica-Bold", fontSize=8, leading=10),
    "rc_r": ParagraphStyle("rc_r", parent=_base, fontSize=8, leading=10, alignment=TA_RIGHT),
}

MODE_LABEL = {
    PaymentMode.CASH: "Cash", PaymentMode.CHEQUE: "Cheque", PaymentMode.UPI: "UPI",
    PaymentMode.NEFT: "NEFT", PaymentMode.RTGS: "RTGS", PaymentMode.BANK_TRANSFER: "Bank Transfer",
    PaymentMode.ONLINE_GATEWAY: "Online",
}

# ── Bill heads ────────────────────────────────────────────────────────────────
# The heads printed on every bill, in order. Lines are grouped into them by
# bill_head(); heads with nothing charged print 0.00.
MAINTENANCE = "Maintenance Charges"
BILL_HEADS = [
    MAINTENANCE, "Sinking Fund", "Repair & Maintenance Fund", "Property Tax",
    "Non Occupancy Charges", "Parking Charges", "Cheque Bounce Charges", "In & Out Charges",
    "Other Charges",
]
# Standard elements that are the society's monthly running expenses — shown
# together as "Maintenance Charges".
MONTHLY_EXPENSE_ELEMENTS = {
    "service_charges", "water_charges", "common_electricity", "lift_maintenance", "security",
    "housekeeping", "insurance", "lease_rent_na_tax", "education_fund", "amenities",
}
_MONTHLY_EXPENSE_TYPES = {ChargeType.MAINTENANCE, ChargeType.WATER, ChargeType.AMENITIES}


def bill_head(line, element_code: Optional[str] = None) -> str:
    """The bill head a line is shown under. `element_code`: the standard
    element the line's charge head was created from, if any."""
    desc = (line.description or "").lower()
    if element_code == "property_tax" or "property tax" in desc or "municipal tax" in desc:
        return "Property Tax"
    if line.charge_type == ChargeType.SINKING_FUND or element_code == "sinking_fund":
        return "Sinking Fund"
    if line.charge_type == ChargeType.REPAIR_FUND or element_code == "repair_fund":
        return "Repair & Maintenance Fund"
    if "non-occupancy" in desc or "non occupancy" in desc:
        return "Non Occupancy Charges"
    if line.charge_type == ChargeType.PARKING or element_code == "parking":
        return "Parking Charges"
    if "cheque" in desc and ("bounce" in desc or "return" in desc or "dishonour" in desc):
        return "Cheque Bounce Charges"
    if "in & out" in desc or "in and out" in desc or "shifting" in desc:
        return "In & Out Charges"
    if element_code in MONTHLY_EXPENSE_ELEMENTS or (
            element_code is None and line.charge_type in _MONTHLY_EXPENSE_TYPES):
        return MAINTENANCE
    return "Other Charges"


# GST on a member's maintenance contribution: services of a membership organisation (SAC 999598), supplied where the
# society's property stands, so within one state — CGST and SGST in equal halves.
GST_SAC = "999598"


def gst_details(society) -> List[tuple]:
    """The SAC Code and Place of Supply rows of a tax invoice: the state is the society's, with the state code (the
    first two digits of its GSTIN) when there is one."""
    state = (society.state or "").strip() if society else ""
    code = (society.gst_number or "").strip()[:2] if society and society.gst_number else ""
    code = code if code.isdigit() else ""
    place = f"{state} ({code})" if state and code else (state or (f"State code {code}" if code else ""))
    return [("SAC Code", GST_SAC)] + ([("Place of Supply", place)] if place else [])


def gst_rows(lines) -> List[tuple]:
    """The tax rows of the heads table: 'CGST @ 9%' and 'SGST @ 9%' (each half of the tax, together exactly the tax)."""
    tax = sum((Decimal(li.tax_amount) for li in lines), ZERO)
    rates = {li.tax_percent.normalize() for li in lines if li.tax_amount}
    half = (tax / 2).quantize(Decimal("0.01"))
    if len(rates) == 1:
        each = f"{next(iter(rates)) / 2:f}%"
        return [(f"CGST @ {each}", half), (f"SGST @ {each}", tax - half)]
    return [("CGST", half), ("SGST", tax - half)]


# ── Formatting helpers ────────────────────────────────────────────────────────

def _inr(v) -> str:
    """Indian digit grouping: 1234567.8 → '12,34,567.80'."""
    v = Decimal(v or 0).quantize(Decimal("0.01"))
    sign = "-" if v < 0 else ""
    whole, frac = f"{abs(v):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_1000(n: int) -> str:
    words = []
    if n >= 100:
        words.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n >= 20:
        words.append(_TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else ""))
    elif n:
        words.append(_ONES[n])
    return " ".join(words)


def _indian_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for size, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand")):
        if n >= size:
            parts.append(f"{_indian_words(n // size) if size == 10**7 else _below_1000(n // size)} {name}")
            n %= size
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def _split(v) -> tuple:
    v = abs(Decimal(v or 0)).quantize(Decimal("0.01"))
    return int(v), int((v - int(v)) * 100)


def amount_in_words(v) -> str:
    """Rs. 6,815.46 → 'Rupees Six Thousand Eight Hundred Fifteen and Paise Forty Six Only'."""
    rupees, paise = _split(v)
    words = f"Rupees {_indian_words(rupees)}"
    if paise:
        words += f" and Paise {_indian_words(paise)}"
    return words + " Only"


def rs_in_words(v) -> str:
    """The bill's style: 3155 → 'Rs. Three Thousand One Hundred Fifty Five only.'"""
    rupees, paise = _split(v)
    words = f"Rs. {_indian_words(rupees)}"
    if paise:
        words += f" and Paise {_indian_words(paise)}"
    return words + " only."


def _d(value: Optional[date]) -> str:
    return value.strftime("%d/%m/%Y") if value else "-"


def _dm(value: Optional[date]) -> str:
    """01-May-2026, as dates read on the bill."""
    return value.strftime("%d-%b-%Y") if value else "-"


def _p(text, style="cell") -> Paragraph:
    return Paragraph(escape(str(text)) if text is not None else "", S[style])


def member(flat, resident=None):
    """The member a bill or receipt is addressed to: the given resident, else
    the flat's primary owner, else any active resident of the flat."""
    if resident:
        return resident
    residents = [r for r in (flat.residents if flat else []) if r.is_active]
    residents.sort(key=lambda r: (not r.is_primary, r.resident_type.value not in ("owner", "co_owner")))
    return residents[0] if residents else None


def member_name(flat, resident=None) -> str:
    m = member(flat, resident)
    return m.full_name if m else "-"


_JOINERS = re.compile(r"\s+(?:&|and)\s+", re.IGNORECASE)


def member_names(flat, resident=None) -> List[str]:
    """The names a bill is addressed to, one per owner: the resident it was raised to first, then the flat's other
    active owners and co-owners (the primary first). A tenant's or family member's bill carries only that person. A name
    entered as "A & B" or "A and B" is two people and is split, so each prints on its own line."""
    def is_owner(r) -> bool:
        return r.resident_type.value in ("owner", "co_owner")

    owners = [r for r in (flat.residents if flat else []) if r.is_active and is_owner(r)]
    owners.sort(key=lambda r: not r.is_primary)
    if resident is not None:
        people = [resident] + [r for r in owners if r is not resident and r.id != resident.id] if is_owner(resident) \
            else [resident]
    else:
        first = member(flat)
        people = owners or ([first] if first else [])
    names: List[str] = []
    for person in people:
        for part in _JOINERS.split(person.full_name or ""):
            part = " ".join(part.split())
            if part and part.lower() not in (n.lower() for n in names):
                names.append(part)
    return names or ["-"]


def flat_label(flat) -> str:
    """'B 304' — wing and flat number."""
    if not flat:
        return "-"
    return f"{flat.wing.name} {flat.flat_number}" if flat.wing else flat.flat_number


def _bill_month(bill: MaintenanceBill) -> str:
    """'Bill for the Month of Aug-2026' — or the period, for a bill covering
    more than one month."""
    cycle = bill.cycle
    start, end = (cycle.cycle_start, cycle.cycle_end) if cycle else (bill.bill_date, bill.bill_date)
    if bill.period_start and bill.period_end:                    # the days actually charged for
        start, end = bill.period_start, bill.period_end
    if (start.year, start.month) == (end.year, end.month):
        return f"Bill for the Month of {start.strftime('%b-%Y')}"
    return f"Bill for the Period {start.strftime('%b-%Y')} to {end.strftime('%b-%Y')}"


def _is_interest(li) -> bool:
    return li.charge_type == ChargeType.PENALTY


def _payments(bill: MaintenanceBill) -> list:
    """(payment, amount set off against the bill): receipts not reversed,
    and recorded payments set off against it (PaymentAllocation) that stand
    — both count towards paid_amount."""
    return [(r, r.amount) for r in bill.receipts if not r.is_reversed] + [
        (a.payment, a.amount) for a in bill.allocations
        if a.released_at is None and a.payment.is_active and a.payment.status != ReconciliationStatus.REJECTED]


def society_header(society, width) -> List:
    """The letterhead: a grey band with the society's name, Regn. No.,
    address and GSTIN/PAN, over a red rule."""
    name = society.name if society else "Society"
    rows = [[_p(name.upper(), "society")]]
    address = ", ".join(x for x in [
        (society.address or "").strip() if society else "", society.city if society else None,
        society.state if society else None] if x)
    if society and society.pincode:
        address = f"{address} {society.pincode}".strip()
    line = " | ".join(x for x in [
        f"Regn. No. {society.registration_number}" if society and society.registration_number else "",
        address.upper()] if x)
    if line:
        rows.append([_p(line, "centre")])
    ids = []
    if society and society.gst_number:
        ids.append(f"GSTIN: {society.gst_number}")
    if society and society.pan_number:
        ids.append(f"PAN: {society.pan_number}")
    if ids:
        rows.append([_p("   |   ".join(ids), "centre")])
    band = Table(rows, colWidths=[width])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("TOPPADDING", (0, 0), (-1, 0), 12), ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
        ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
    ]))
    return [band, HRFlowable(width="100%", thickness=2.5, color=RED, spaceBefore=0, spaceAfter=0)]


def sign_off(society_name: str, width, note: str) -> Table:
    """'For <SOCIETY>', the signature line, Hon. Secretary / Treasurer / Chairman."""
    sign = Table([
        [_p(note, "small"), _p(f"For {society_name.upper()}", "sign")],
        ["", Spacer(1, 8 * mm)],
        ["", _p("HON. SECRETARY / TREASURER / CHAIRMAN", "sign")],
    ], colWidths=[width * 0.45, width * 0.55])
    sign.setStyle(TableStyle([
        ("LINEABOVE", (1, 2), (1, 2), 1.4, INK),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (1, 0), (1, -1), 20), ("RIGHTPADDING", (1, 0), (1, -1), 10),
    ]))
    return sign


COLON_W = 2.5 * mm


def _kv(rows, widths) -> Table:
    """Label / ':' / value triples, as in the bill's details box. `widths` is (label, value); the colon has a column of
    its own so a value that runs to several lines (two owners' names) stays under its first line, not under the label."""
    t = Table([[_p(k, "cell_b"), _p(":"), Paragraph(v, S["cell"])] for k, v in rows],
              colWidths=[widths[0], COLON_W, widths[1] - COLON_W])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ── The bill ──────────────────────────────────────────────────────────────────

PAGE_MARGINS = dict(leftMargin=12 * mm, rightMargin=12 * mm, topMargin=8 * mm, bottomMargin=10 * mm)


def _expense_statements(bill: MaintenanceBill) -> List[str]:
    """One note for each head on this bill that was worked out from the society's actual expenses of a period: what
    was spent, how it was shared and the flat's share. Only for lines tied to a recorded allocation (the snapshot made
    when the bills were generated) - the printed working is the stored one, never a recomputation."""
    seen, out = set(), []
    for li in bill.line_items:
        alloc = getattr(li, "allocation", None)
        if alloc is None or alloc.id in seen:
            continue
        seen.add(alloc.id)
        mine = sum((Decimal(l.amount or 0) for l in bill.line_items if l.allocation_id == alloc.id), ZERO)
        if alloc.method == "area":
            how = f"in proportion to flat area (Rs. {Decimal(alloc.rate):,.4f} per sq ft for the full period)"
        else:
            how = f"equally between flats (Rs. {Decimal(alloc.rate):,.4f} per flat for the full period)"
        what = f" on {escape(alloc.element_name)}" if alloc.element_name else ""
        spent = sum((Decimal(src.amount or 0) for src in alloc.sources), ZERO)
        if spent > Decimal(alloc.pool_amount):
            # Made again after other bills of the cycle were issued: only what those bills did not take is shared.
            out.append(
                f"<b>{escape(alloc.charge_name)}</b> is the society's actual expenses{what} from "
                f"{alloc.period_start:%d %b %Y} to {alloc.period_end:%d %b %Y}: Rs. {_inr(spent)} in all, of which "
                f"Rs. {_inr(alloc.pool_amount)} was not on bills already issued. That balance is shared {how} over "
                f"{alloc.eligible_flats} flat(s). Your share: Rs. {_inr(mine)}.")
            continue
        out.append(
            f"<b>{escape(alloc.charge_name)}</b> is the society's actual expenses{what} from "
            f"{alloc.period_start:%d %b %Y} to {alloc.period_end:%d %b %Y}: Rs. {_inr(alloc.pool_amount)} in all, "
            f"shared {how} over {alloc.eligible_flats} flat(s). Your share: Rs. {_inr(mine)}. Shares are rounded to the "
            f"paisa so that the shares add up to exactly Rs. {_inr(alloc.pool_amount)}.")
    return out


def generate_maintenance_bill_pdf(
    bill: MaintenanceBill,
    settings: Optional[MaintenanceSettings] = None,
    *,
    compress: bool = True,
    element_codes: Optional[Dict[str, str]] = None,
    element_names: Optional[Dict[str, str]] = None,
    accumulated_interest: Decimal = ZERO,
    previous_bill: Optional[MaintenanceBill] = None,
) -> bytes:
    """`element_codes`: {charge head name: standard element code} — decides
    which lines are monthly expenses. `accumulated_interest`: the unpaid
    interest inside the bill's arrears (Previous Interest/Late Fees).
    `previous_bill`: the flat's bill before this one, whose receipts are
    listed at the foot."""
    society = bill.society
    society_name = society.name if society else "Society"
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title=f"Maintenance Bill {bill.invoice_number}",
        author=society_name, pageCompression=1 if compress else 0, **PAGE_MARGINS,
    )
    doc.build(bill_story(bill, settings, doc.width, element_codes=element_codes, element_names=element_names,
                         accumulated_interest=accumulated_interest, previous_bill=previous_bill))
    return buf.getvalue()


def generate_bills_pdf(bills: List[dict], *, title: str, author: str, compress: bool = True) -> bytes:
    """Many bills in one PDF, each on its own page(s), in the order given. Each item is the keyword arguments of
    `bill_story` plus `bill` and `settings`: {"bill", "settings", "element_codes", "accumulated_interest",
    "previous_bill"}."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title, author=author, pageCompression=1 if compress else 0,
                            **PAGE_MARGINS)
    story: List = []
    for i, item in enumerate(bills):
        if i:
            story.append(PageBreak())
        story += bill_story(item["bill"], item.get("settings"), doc.width,
                            element_codes=item.get("element_codes"), element_names=item.get("element_names"),
                            accumulated_interest=item.get("accumulated_interest", ZERO),
                            previous_bill=item.get("previous_bill"))
    doc.build(story)
    return buf.getvalue()


def bill_story(
    bill: MaintenanceBill,
    settings: Optional[MaintenanceSettings],
    width: float,
    *,
    element_codes: Optional[Dict[str, str]] = None,
    element_names: Optional[Dict[str, str]] = None,
    accumulated_interest: Decimal = ZERO,
    previous_bill: Optional[MaintenanceBill] = None,
) -> List:
    """The flowables of one printed bill (the letterhead down to the receipts towards the previous bill), in the layout
    the society chose (`MaintenanceSettings.bill_layout`)."""
    if settings is not None and getattr(settings, "bill_layout", None) == "classic":
        return classic_bill_story(bill, settings, width, element_codes=element_codes, element_names=element_names,
                                  accumulated_interest=accumulated_interest, previous_bill=previous_bill)
    element_codes = element_codes or {}
    society = bill.society
    society_name = society.name if society else "Society"
    flat = bill.flat
    story: List = []
    story += society_header(society, width)
    story.append(Spacer(1, 4 * mm))

    gst_charged = (bill.tax_amount or 0) > 0
    status = bill.bill_status.value
    story.append(_p("Maintenance Bill" + (" / Tax Invoice" if gst_charged else ""), "title"))
    if status == "cancelled":
        story.append(Paragraph("<font color='#B91C1C'><b>CANCELLED</b></font>", S["cell_c"]))
    story.append(Spacer(1, 3 * mm))

    # ── Member and bill details ──
    m = member(flat, bill.resident)
    email = m.email if m and m.email and not m.email.endswith("@duxos.local") else ""
    area = f"{flat.area_sqft:,.0f}" if flat and flat.area_sqft else ""
    cycle = bill.cycle
    p_start = (bill.period_start or cycle.cycle_start) if cycle else None
    p_end = (bill.period_end or cycle.cycle_end) if cycle else None
    period = f"{_dm(p_start)} to {_dm(p_end)}" if cycle else ""
    left = _kv([
        ("Name", "<br/>".join(f"<b>{escape(n)}</b>" for n in member_names(flat, bill.resident))),
        ("Flat No.", escape(flat_label(flat))),
        ("Area sq ft", area),
        ("Mobile No", escape(m.phone or "") if m else ""),
        ("Mail ID", escape(email)),
    ], [24 * mm, width * 0.5 - 12 - 24 * mm - 8])
    van = flat.virtual_account_number if flat else None
    right = _kv([
        ("Bill No.", escape(bill.invoice_number)),
        ("Bill Date", _dm(bill.bill_date)),
        ("Due Date", _dm(bill.due_date)),
        ("Bill Period", period),
        *([("Virtual A/c No.(VAN)", escape(van))] if van else []),
        *[(k, escape(v)) for k, v in (gst_details(society) if gst_charged else [])],
    ], [33 * mm, width * 0.5 - 12 - 33 * mm - 8])
    box = Table([[left, right]], colWidths=[width * 0.5, width * 0.5])
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(box)
    story.append(Spacer(1, 4 * mm))

    # ── Heads ──
    lines = [li for li in bill.line_items if not _is_interest(li)]
    amount_of = (lambda li: li.amount) if gst_charged else (lambda li: li.total)
    by_head: Dict[str, Decimal] = {h: ZERO for h in BILL_HEADS}
    for li in lines:
        by_head[bill_head(li, element_codes.get(li.description))] += Decimal(amount_of(li))
    heads = list(by_head.items())
    if gst_charged:
        heads += gst_rows(lines)

    current = sum((Decimal(li.total) for li in lines), ZERO)
    current_interest = (sum((Decimal(li.total) for li in bill.line_items if _is_interest(li)), ZERO)
                        + Decimal(bill.penalty_amount or 0))
    arrears_total = Decimal(bill.previous_dues or 0)
    prev_interest = min(max(Decimal(accumulated_interest or 0), ZERO), max(arrears_total, ZERO))
    arrears = arrears_total - prev_interest
    discount = Decimal(bill.discount_amount or 0)
    round_off = Decimal(bill.round_off or 0)
    payable = current + arrears + current_interest + prev_interest - discount + round_off

    amt_w = 40 * mm
    data = [[_p("No", "cell_b"), _p("Head", "cell_b"), _p("Amount (Rs.)", "cell_rb")]]
    data += [[_p(i), _p(name), _p(_inr(amount), "cell_r")] for i, (name, amount) in enumerate(heads, 1)]
    first_summary = len(data)
    # Summary rows: the label spans No + Head, so it sits in the first cell
    data.append([_p("Current Bill Amount", "cell_rb"), "", _p(_inr(current), "cell_rb")])
    summary = [("Arrears/Advances", arrears), ("Current Interest/ Late Fees", current_interest),
               ("Previous Interest/ Late Fees", prev_interest)]
    if discount:
        summary.append(("Less: Discount", -discount))
    if round_off:
        summary.append(("Round off", round_off))
    for label, amount in summary:
        data.append([_p(label, "cell_r"), "", _p(_inr(amount), "cell_r")])
    data.append([_p("Total Maintenance Payable Amount", "cell_rb"), "", _p(f"Rs. {_inr(payable)}", "cell_rb")])
    last = len(data) - 1
    t = Table(data, colWidths=[9 * mm, width - 9 * mm - amt_w, amt_w], repeatRows=1)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), BAND), ("LINEBELOW", (0, 0), (-1, 0), 0.8, RULE),
        ("LINEAFTER", (0, 0), (0, first_summary - 1), 0.8, RULE),
        ("LINEBEFORE", (2, 0), (2, -1), 0.8, RULE),
        *[("SPAN", (0, r), (1, r)) for r in range(first_summary, len(data))],
        ("BACKGROUND", (0, first_summary), (-1, first_summary), BAND),
        ("LINEABOVE", (0, first_summary), (-1, first_summary), 0.8, RULE),
        ("LINEBELOW", (0, first_summary), (-1, first_summary), 0.8, RULE),
        ("BACKGROUND", (0, last), (-1, last), BAND),
        ("LINEABOVE", (0, last), (-1, last), 0.8, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 1), (-1, -1), 0.8),
        ("TOPPADDING", (0, 0), (-1, 0), 2.5), ("BOTTOMPADDING", (0, 0), (-1, 0), 2.5),
        ("TOPPADDING", (0, first_summary), (-1, first_summary), 2.5),
        ("BOTTOMPADDING", (0, first_summary), (-1, first_summary), 2.5),
        ("TOPPADDING", (0, last), (-1, last), 2.5), ("BOTTOMPADDING", (0, last), (-1, last), 2.5),
    ]))
    story.append(t)
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"<b>Amount payable in words:</b> {escape(rs_in_words(payable))}", S["cell"]))
    story.append(Spacer(1, 3.5 * mm))
    working = _interest_working_table(bill, width)
    if working is not None:
        story += [working, Spacer(1, 5 * mm)]

    # ── Notes ──
    notes: List[str] = []
    if settings and (settings.bank_account_number or settings.upi_id or van):
        pay_to = settings.bank_account_name or society_name
        notes.append("We recommend payment through NEFT, giving following details")
        sub = [f"(a) <b>Beneficiary Name: {escape(pay_to.upper())}</b>"]
        # A flat with a virtual account number pays to it, so the bank can
        # tell which flat paid.
        account = "Virtual Ac No Mentioned Above in Bill" if van else settings.bank_account_number
        if account:
            acct = f"(b) <b>Account No: {escape(account)}</b>"
            if settings.bank_ifsc:
                acct += f" with <b>IFSC Code: {escape(settings.bank_ifsc)}</b>"
            sub.append(acct)
        if settings.bank_name:
            sub.append(f"({chr(97 + len(sub))}) <b>Bank: {escape(settings.bank_name)}</b>")
        if settings.upi_id:
            sub.append(f"({chr(97 + len(sub))}) <b>UPI ID: {escape(settings.upi_id)}</b>")
        notes += ["&nbsp;" + x for x in sub]
    rate = Decimal(settings.interest_rate_pct) if settings and settings.interest_rate_pct is not None else None
    if rate and rate > 0:
        grace = settings.interest_grace_days or 0
        notes.append(f"Interest @ {rate.normalize():f}% p.a. will be charged on dues not paid by the due date"
                     + (f" (grace period {grace} days)." if grace else "."))
    notes += _expense_statements(bill)
    notes.append("Any queries related to the bill should be raised within 7 days of bill issuance "
                 "to the society office.")
    notes.append("Outstanding dues are subject to final audit.")
    if settings and settings.bill_notes:
        notes += [escape(line.strip()) for line in settings.bill_notes.splitlines() if line.strip()]
    # A "Notes" tab over the notes box, as one table so the two line up
    note_rows = [[_p("Notes", "tab"), ""]] + [
        [Paragraph(n if n.startswith("&nbsp;") else f"* {n}", S["note"]), ""] for n in notes]
    nb = Table(note_rows, colWidths=[40 * mm, width - 40 * mm])
    nb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), BAND), ("BOX", (0, 0), (0, 0), 0.8, RULE),
        ("BOX", (0, 1), (-1, -1), 0.8, RULE),
        *[("SPAN", (0, r), (1, r)) for r in range(1, len(note_rows))],
        ("LEFTPADDING", (0, 1), (-1, -1), 4), ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (0, 0), 3), ("BOTTOMPADDING", (0, 0), (0, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
    ]))
    story.append(nb)
    story.append(Spacer(1, 10 * mm))

    # ── Footer rule, and the receipts towards the previous bill ──
    rule = HRFlowable(width="100%", thickness=2, color=RED)
    foot = Table([[rule, _p("This is a Computer Generated bill, hence no signature is required.", "foot"),
                   HRFlowable(width="100%", thickness=2, color=RED)]],
                 colWidths=[width * 0.22, width * 0.56, width * 0.22])
    foot.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    block = [foot]
    if previous_bill is not None:
        block += [Spacer(1, 3 * mm), _receipts_table(previous_bill, width)]
    story.append(KeepTogether(block))

    return story


# ── The classic layout ────────────────────────────────────────────────────────
# Every charge head on its own line (heads not charged print 0.00), the totals box, numbered notes, and the receipt slip
# for the flat's previous bill at the foot over the signature line: the layout many older societies still print.

def _classic_notes(bill: MaintenanceBill, settings: Optional[MaintenanceSettings], society_name: str, van) -> List[str]:
    notes: List[str] = []
    rate = Decimal(settings.interest_rate_pct) if settings and settings.interest_rate_pct is not None else None
    if rate and rate > 0:
        grace = settings.interest_grace_days or 0
        notes.append(f"Interest @ {rate.normalize():f}% p.a. will be charged on dues not paid by the due date"
                     + (f" (grace period {grace} days)." if grace else "."))
    notes.append("Please inform the society office within 7 days in case of any discrepancy.")
    notes.append("Please mention your flat no. and bill no. on the back of the cheque.")
    if settings and (settings.bank_account_number or settings.upi_id or van):
        pay_to = settings.bank_account_name or society_name
        line = f"You can pay by NEFT to <b>{escape(pay_to.upper())}</b>"
        account = "your Virtual A/c No. shown above" if van else settings.bank_account_number
        if account:
            line += f", A/c No. <b>{escape(account)}</b>"
        if settings.bank_ifsc:
            line += f", IFSC <b>{escape(settings.bank_ifsc)}</b>"
        if settings.bank_name:
            line += f", {escape(settings.bank_name)}"
        if settings.upi_id:
            line += f", or UPI <b>{escape(settings.upi_id)}</b>"
        notes.append(line + ".")
    notes.append("Receipts are subject to realisation of the cheque.")
    notes += _expense_statements(bill)
    notes.append("Outstanding dues are subject to final audit.")
    if settings and settings.bill_notes:
        notes += [escape(line.strip()) for line in settings.bill_notes.splitlines() if line.strip()]
    return notes


def _receipt_slip(prev: MaintenanceBill, payment, amount, flat, resident, width) -> Table:
    """One payment received towards the previous bill, as the slip printed at the foot of the classic bill."""
    cheque = payment.payment_mode == PaymentMode.CHEQUE
    ref = (getattr(payment, "cheque_number", None) or payment.transaction_ref or "") \
        if payment.payment_mode != PaymentMode.CASH else ""
    mode = MODE_LABEL.get(payment.payment_mode, payment.payment_mode.value)
    vide = " ".join(x for x in [mode, ref, payment.bank_name if cheque and payment.bank_name else ""] if x)
    who = member_names(flat, resident)
    amt_box = Table([[_p(f"Rs. {_inr(amount)}", "cell_rb")]], colWidths=[40 * mm])
    amt_box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, RULE), ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                                 ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    rows = [
        [Paragraph("<font color='#0B4A8B'><b><u>RECEIPT for Previous Bill</u></b></font>", S["cell_c"]), "", ""],
        [Paragraph(f"Receipt No.: <b>{escape(payment.receipt_number)}</b>", S["cell"]), "",
         Paragraph(f"Date : <b>{payment.payment_date.strftime('%d/%m/%Y')}</b>", S["cell_r"])],
        [Paragraph("Received with thanks from <b>" + escape(" & ".join(who)) + "</b>", S["cell"]), "",
         Paragraph(f"<b>{escape(flat_label(flat))}</b>", S["cell_r"])],
        [_p(rs_in_words(amount)), "", amt_box],
        [Paragraph(f"Vide {escape(vide)}" if vide else "Vide Cash", S["cell"]), "",
         _p("Subject to realisation of cheque" if cheque else "", "small_r")],
        [Paragraph(f"Towards Bill No. {escape(prev.invoice_number)} Dated : {_dm(prev.bill_date)}", S["cell"]), "", ""],
    ]
    t = Table(rows, colWidths=[width * 0.5, width * 0.1, width * 0.4])
    t.setStyle(TableStyle([
        ("ROUNDEDCORNERS", [6, 6, 6, 6]), ("BOX", (0, 0), (-1, -1), 0.8, RULE),
        ("SPAN", (0, 0), (-1, 0)), ("SPAN", (0, 1), (1, 1)), ("SPAN", (0, 2), (1, 2)), ("SPAN", (0, 3), (1, 3)),
        ("SPAN", (0, 4), (1, 4)), ("SPAN", (0, 5), (-1, 5)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
    ]))
    return t


def classic_bill_story(
    bill: MaintenanceBill,
    settings: Optional[MaintenanceSettings],
    width: float,
    *,
    element_codes: Optional[Dict[str, str]] = None,
    element_names: Optional[Dict[str, str]] = None,
    accumulated_interest: Decimal = ZERO,
    previous_bill: Optional[MaintenanceBill] = None,
) -> List:
    """The flowables of one bill in the classic layout. The same figures as the standard layout, laid out differently:
    each maintenance element is its own line (a charge head prints under the name of the element it was made from, and
    two heads of one element add up to one line), the totals sit in one box with the amount in words, the notes are numbered, and the
    receipts for the previous bill print as slips above the signature line."""
    element_codes = element_codes or {}
    element_names = element_names or {}
    society = bill.society
    society_name = society.name if society else "Society"
    flat = bill.flat
    story: List = []

    # ── Letterhead: a rounded box, the name in blue ──
    address = ", ".join(x for x in [
        (society.address or "").strip() if society else "", society.city if society else None,
        society.state if society else None] if x)
    if society and society.pincode:
        address = f"{address} {society.pincode}".strip()
    name_style = ParagraphStyle("classic_name", parent=S["society"], fontSize=17, leading=21, textColor=ACCENT)
    head_rows = [[Paragraph(escape(society_name.upper()), name_style)]]
    if society and society.registration_number:
        head_rows.append([_p(f"Regn. No. {society.registration_number}", "centre")])
    if address:
        head_rows.append([_p(address.upper(), "centre")])
    ids = [x for x in [f"GSTIN: {society.gst_number}" if society and society.gst_number else "",
                       f"PAN: {society.pan_number}" if society and society.pan_number else ""] if x]
    if ids:
        head_rows.append([_p("   |   ".join(ids), "centre_small")])
    head = Table(head_rows, colWidths=[width])
    head.setStyle(TableStyle([
        ("ROUNDEDCORNERS", [8, 8, 8, 8]), ("BOX", (0, 0), (-1, -1), 0.8, RULE),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
    ]))
    story += [head, Spacer(1, 4 * mm)]

    gst_charged = (bill.tax_amount or 0) > 0
    if bill.bill_status.value == "cancelled":
        story += [Paragraph("<font color='#B91C1C'><b>CANCELLED</b></font>", S["cell_c"]), Spacer(1, 2 * mm)]

    # ── Who the bill is for, and its numbers ──
    m = member(flat, bill.resident)
    area = f"{flat.area_sqft:,.0f}" if flat and flat.area_sqft else ""
    van = flat.virtual_account_number if flat else None
    names = "<br/>".join(f"<b>{escape(n)}</b>" for n in member_names(flat, bill.resident))
    big = ParagraphStyle("classic_big", parent=S["cell_b"], fontSize=11, leading=14)
    left = Table([
        [Paragraph(f"<b>{escape(_bill_month(bill))}</b>", S["cell"]), ""],
        [_p("Name :"), Paragraph(names, ParagraphStyle("classic_names", parent=S["cell"], fontSize=10, leading=13))],
        [_p("FLAT NO"), Paragraph(escape(flat_label(flat)), big)],
    ], colWidths=[18 * mm, width * 0.5 - 18 * mm - 4])
    left.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    rows = [("Bill No.", escape(bill.invoice_number)), ("Bill Date", _d(bill.bill_date)),
            ("Due Date", f"<b>{_d(bill.due_date)}</b>")]
    if area:
        rows.append(("Area Carpet", f"{area} Sq. Feet"))
    if van:
        rows.append(("Virtual A/c No.", escape(van)))
    if gst_charged:
        rows += [(k, escape(v)) for k, v in gst_details(society)]
    right = _kv(rows, [28 * mm, width * 0.5 - 4 - 28 * mm])
    top = Table([[left, right]], colWidths=[width * 0.5, width * 0.5])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 2),
                             ("LEFTPADDING", (1, 0), (1, 0), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [top, Spacer(1, 4 * mm)]

    # ── Particulars: every head on its own line; heads not charged this time print 0.00 ──
    lines = [li for li in bill.line_items if not _is_interest(li)]
    amount_of = (lambda li: li.amount) if gst_charged else (lambda li: li.total)
    def element_of(description: str) -> str:
        return element_names.get(description, description)

    charged: Dict[str, Decimal] = {}
    for li in lines:
        name = element_of(li.description)
        charged[name] = charged.get(name, ZERO) + Decimal(amount_of(li))
    # the society's other elements, so the bill shows every element it levies (0.00 where nothing is charged this time)
    others = sorted({element_of(head) for head in (element_names or element_codes)} - set(charged))
    heads = list(charged.items()) + [(name, ZERO) for name in others]
    if gst_charged:
        heads += gst_rows(lines)

    current = sum((Decimal(li.total) for li in lines), ZERO)
    current_interest = (sum((Decimal(li.total) for li in bill.line_items if _is_interest(li)), ZERO)
                        + Decimal(bill.penalty_amount or 0))
    arrears_total = Decimal(bill.previous_dues or 0)
    prev_interest = min(max(Decimal(accumulated_interest or 0), ZERO), max(arrears_total, ZERO))
    arrears = arrears_total - prev_interest
    discount = Decimal(bill.discount_amount or 0)
    round_off = Decimal(bill.round_off or 0)
    payable = current + arrears + current_interest + prev_interest - discount + round_off

    amt_w = 42 * mm
    spaced = ParagraphStyle("classic_spaced", parent=S["cell"], fontSize=9, leading=11, spaceBefore=0)
    data = [[Paragraph("P a r t i c u l a r s", spaced), Paragraph("Amount (in Rs.)", S["cell_r"])]]
    data += [[_p(name), _p(_inr(amount), "cell_r")] for name, amount in heads]
    heads_end = len(data) - 1
    t1 = Table(data, colWidths=[width - amt_w, amt_w])
    t1.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, INK), ("LINEBELOW", (0, 0), (-1, 0), 1, INK), ("LINEBEFORE", (1, 0), (1, -1), 1, INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, 0), 3), ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("BOTTOMPADDING", (0, heads_end), (-1, heads_end), 8),
    ]))

    summary = [("Total :", current, False), ("Arrears / Advance :", arrears, False),
               ("Accumulated Interest :", prev_interest, False),
               ("Current Interest / Late Fees :", current_interest, False)]
    if discount:
        summary.append(("Less: Discount :", -discount, False))
    if round_off:
        summary.append(("Round off :", round_off, False))
    summary.append(("Grand Total :", payable, True))
    srows = [[_p(rs_in_words(payable)), _p(label, "cell_rb" if bold else "cell_r"),
              _p(_inr(amount), "cell_rb" if bold else "cell_r")] for label, amount, bold in summary]
    for r in srows[1:]:
        r[0] = ""
    t2 = Table(srows, colWidths=[(width - amt_w) * 0.42, (width - amt_w) * 0.58, amt_w])
    t2.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, INK), ("LINEBEFORE", (2, 0), (2, -1), 1, INK),
        ("SPAN", (0, 0), (0, -1)), ("VALIGN", (0, 0), (0, 0), "TOP"), ("VALIGN", (1, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, RULE),
    ]))
    story += [t1, t2, Spacer(1, 3 * mm)]
    working = _interest_working_table(bill, width)
    if working is not None:
        story += [working, Spacer(1, 3 * mm)]

    # ── Numbered notes ──
    notes_style = ParagraphStyle("classic_notes", parent=S["note"], fontSize=8, leading=10.5)
    story.append(_p("Notes :", "small"))
    story += [Paragraph(f"{i}. {n}", notes_style) for i, n in enumerate(_classic_notes(bill, settings, society_name, van), 1)]
    story.append(Spacer(1, 4 * mm))

    # ── The receipt slip(s) for the previous bill, and the signature line ──
    block: List = []
    if previous_bill is not None:
        paid = sorted(_payments(previous_bill), key=lambda pa: (pa[0].payment_date, pa[0].receipt_number))
        for payment, amount in paid[-3:]:            # the latest three; earlier ones are on their own receipts
            block += [_receipt_slip(previous_bill, payment, amount, flat, bill.resident, width),
                      Spacer(1, 3 * mm)]
    block.append(sign_off(society_name, width, ""))
    story.append(KeepTogether(block))
    return story


def _interest_working_table(bill: MaintenanceBill, width) -> Optional[Table]:
    """'Interest working': for each earlier bill the interest was charged on, the unpaid amount, the days it ran and the
    rate, so a member can check the Interest line. Nothing for a bill with no interest or made before this was kept."""
    try:
        rows_in = json.loads(bill.interest_working) if bill.interest_working else []
    except ValueError:
        rows_in = []
    if not rows_in:
        return None

    def day(iso):
        return date.fromisoformat(iso).strftime("%d-%b-%y")

    head = ["Bill No.", "Unpaid (Rs.)", "From", "To", "Days", "Rate % p.a.", "Interest (Rs.)"]
    rows = [[_p("Interest working", "cell_cb")] + [""] * 6, [_p(h, "rc_b") for h in head]]
    total = ZERO
    for r in rows_in:
        total += Decimal(r["interest"])
        rows.append([_p(r["bill"], "rc"), _p(_inr(Decimal(r["principal"])), "rc_r"), _p(day(r["from"]), "rc"),
                     _p(day(r["to"]), "rc"), _p(str(r["days"]), "rc_r"), _p(r["rate"], "rc_r"),
                     _p(_inr(Decimal(r["interest"])), "rc_r")])
    rows.append([_p("Total interest", "rc_b")] + [""] * 5 + [_p(_inr(total), "rc_r")])
    widths = [30 * mm, 26 * mm, 22 * mm, 22 * mm, 14 * mm, 22 * mm]
    widths.append(width - sum(widths))
    last = len(rows) - 1
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, RULE), ("INNERGRID", (0, 1), (-1, -1), 0.6, RULE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE), ("SPAN", (0, 0), (-1, 0)), ("SPAN", (0, last), (5, last)),
        ("BACKGROUND", (0, last), (-1, last), BAND),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _receipts_table(prev: MaintenanceBill, width) -> Table:
    """'Receipts: Towards Bill No. X for Apr-2026' — the payments received
    against the flat's previous bill."""
    month = prev.cycle.cycle_start.strftime("%b-%Y") if prev.cycle else prev.bill_date.strftime("%b-%Y")
    head = ["Receipt No.", "Date", "Amount", "Tra. Type", "Reference No.", "Cheque Bank Name", "Narration:"]
    rows = [[_p(f"Receipts: Towards Bill No. {prev.invoice_number} for {month}", "cell_cb")] + [""] * 6,
            [_p(h, "rc_b") for h in head]]
    paid = sorted(_payments(prev), key=lambda pa: (pa[0].payment_date, pa[0].receipt_number))
    for p, amount in paid:
        cheque = p.payment_mode == PaymentMode.CHEQUE
        ref = (getattr(p, "cheque_number", None) or p.transaction_ref or "") if p.payment_mode != PaymentMode.CASH else ""
        narration = (p.notes or "").strip() or f"Maintenance paid for {month}"
        rows.append([_p(p.receipt_number, "rc"), _p(p.payment_date.strftime("%d-%b-%y"), "rc"),
                     _p(_inr(amount), "rc_r"), _p(MODE_LABEL.get(p.payment_mode, p.payment_mode.value).upper(), "rc"),
                     _p(ref, "rc"), _p(p.bank_name if cheque and p.bank_name else "", "rc"), _p(narration, "rc")])
    if not paid:
        rows.append([_p("No receipts against this bill.", "rc")] + [""] * 6)
    widths = [26 * mm, 17 * mm, 20 * mm, 22 * mm, 28 * mm, 28 * mm]
    widths.append(width - sum(widths))
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, RULE), ("INNERGRID", (0, 1), (-1, -1), 0.6, RULE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE), ("SPAN", (0, 0), (-1, 0)),
        *([("SPAN", (0, 2), (-1, 2))] if not paid else []),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t
