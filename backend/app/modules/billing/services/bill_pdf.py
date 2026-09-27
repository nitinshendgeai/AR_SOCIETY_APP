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
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
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
    if (start.year, start.month) == (end.year, end.month):
        return f"Bill for the Month of {start.strftime('%b-%Y')}"
    return f"Bill for the Period {start.strftime('%b-%Y')} to {end.strftime('%b-%Y')}"


def _is_interest(li) -> bool:
    return li.charge_type == ChargeType.PENALTY


def _payments(bill: MaintenanceBill) -> list:
    """Payments that count against a bill: receipts not reversed, and on-bill
    payments not rejected (both count towards paid_amount)."""
    return [r for r in bill.receipts if not r.is_reversed] + [
        s for s in bill.online_payments if s.is_active and s.status != ReconciliationStatus.REJECTED]


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


def _kv(rows, widths) -> Table:
    """Label / ': value' pairs, as in the bill's details box."""
    t = Table([[_p(k, "cell_b"), Paragraph(f": {v}", S["cell"])] for k, v in rows], colWidths=widths)
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ── The bill ──────────────────────────────────────────────────────────────────

def generate_maintenance_bill_pdf(
    bill: MaintenanceBill,
    settings: Optional[MaintenanceSettings] = None,
    *,
    compress: bool = True,
    element_codes: Optional[Dict[str, str]] = None,
    accumulated_interest: Decimal = ZERO,
    previous_bill: Optional[MaintenanceBill] = None,
) -> bytes:
    """`element_codes`: {charge head name: standard element code} — decides
    which lines are monthly expenses. `accumulated_interest`: the unpaid
    interest inside the bill's arrears (Previous Interest/Late Fees).
    `previous_bill`: the flat's bill before this one, whose receipts are
    listed at the foot."""
    element_codes = element_codes or {}
    society = bill.society
    society_name = society.name if society else "Society"
    flat = bill.flat
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=8 * mm,
        bottomMargin=10 * mm, title=f"Maintenance Bill {bill.invoice_number}",
        author=society_name, pageCompression=1 if compress else 0,
    )
    width = doc.width
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
    period = f"{_dm(cycle.cycle_start)} to {_dm(cycle.cycle_end)}" if cycle else ""
    left = _kv([
        ("Name", f"<b>{escape(member_name(flat, bill.resident))}</b>"),
        ("Flat No.", escape(flat_label(flat))),
        ("Area sq ft", area),
        ("Mobile No", escape(m.phone or "") if m else ""),
        ("Mail ID", escape(email)),
    ], [36 * mm, width * 0.55 - 28 * mm])
    right = _kv([
        ("Bill No.", escape(bill.invoice_number)),
        ("Bill Date", _dm(bill.bill_date)),
        ("Due Date", _dm(bill.due_date)),
        ("Bill Period", period),
    ], [24 * mm, width * 0.45 - 28 * mm])
    box = Table([[left, right]], colWidths=[width * 0.55, width * 0.45])
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
        rates = {li.tax_percent.normalize() for li in lines if li.tax_amount}
        label = f"GST @ {next(iter(rates)):f}%" if len(rates) == 1 else "GST"
        heads.append((label, sum((Decimal(li.tax_amount) for li in lines), ZERO)))

    current = sum((Decimal(li.total) for li in lines), ZERO)
    current_interest = (sum((Decimal(li.total) for li in bill.line_items if _is_interest(li)), ZERO)
                        + Decimal(bill.penalty_amount or 0))
    arrears_total = Decimal(bill.previous_dues or 0)
    prev_interest = min(max(Decimal(accumulated_interest or 0), ZERO), max(arrears_total, ZERO))
    arrears = arrears_total - prev_interest
    discount = Decimal(bill.discount_amount or 0)
    payable = current + arrears + current_interest + prev_interest - discount

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
    story.append(Spacer(1, 5 * mm))

    # ── Notes ──
    notes: List[str] = []
    if settings and (settings.bank_account_number or settings.upi_id):
        pay_to = settings.bank_account_name or society_name
        notes.append("We recommend payment through NEFT, giving following details")
        sub = [f"(a) <b>Beneficiary Name: {escape(pay_to.upper())}</b>"]
        if settings.bank_account_number:
            acct = f"(b) <b>Account No: {escape(settings.bank_account_number)}</b>"
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
    notes.append("Any queries related to the bill should be raised within 7 days of bill issuance "
                 "to the society office.")
    notes.append("Outstanding dues are subject to final audit.")
    if settings and settings.bill_notes:
        notes += [escape(line.strip()) for line in settings.bill_notes.splitlines() if line.strip()]
    notes.append("This is computer generated bill hence signature is not required.")
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

    doc.build(story)
    return buf.getvalue()


def _receipts_table(prev: MaintenanceBill, width) -> Table:
    """'Receipts: Towards Bill No. X for Apr-2026' — the payments received
    against the flat's previous bill."""
    month = prev.cycle.cycle_start.strftime("%b-%Y") if prev.cycle else prev.bill_date.strftime("%b-%Y")
    head = ["Receipt No.", "Date", "Amount", "Tra. Type", "Reference No.", "Cheque Bank Name", "Narration:"]
    rows = [[_p(f"Receipts: Towards Bill No. {prev.invoice_number} for {month}", "cell_cb")] + [""] * 6,
            [_p(h, "rc_b") for h in head]]
    paid = sorted(_payments(prev), key=lambda p: (p.payment_date, p.receipt_number))
    for p in paid:
        cheque = p.payment_mode == PaymentMode.CHEQUE
        ref = (getattr(p, "cheque_number", None) or p.transaction_ref or "") if p.payment_mode != PaymentMode.CASH else ""
        narration = (p.notes or "").strip() or f"Maintenance paid for {month}"
        rows.append([_p(p.receipt_number, "rc"), _p(p.payment_date.strftime("%d-%b-%y"), "rc"),
                     _p(_inr(p.amount), "rc_r"), _p(MODE_LABEL.get(p.payment_mode, p.payment_mode.value).upper(), "rc"),
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
