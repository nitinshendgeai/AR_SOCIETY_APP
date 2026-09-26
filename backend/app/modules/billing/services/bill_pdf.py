"""A4 PDF for a MaintenanceBill in the layout Mumbai co-operative housing
societies use for their monthly bill (Maharashtra model bye-laws: charges
under the heads of bye-law 65-67, arrears and interest on arrears shown on
the bill):

- a boxed header: society name, registration number, address (GSTIN/PAN
  when set);
- "Bill for the Month of <Mon-YYYY>", member name and flat on the left;
  bill no., bill date, due date and carpet area on the right;
- the Particulars table: every charge head of the society, with 0.00 for
  the heads this flat isn't charged; below it the principal arrears and
  accumulated interest on the left, and Total / Arrears / Interest on
  arrears / Grand Total on the right, with the grand total in words;
- numbered notes (discrepancies, interest on unpaid bills, how to pay,
  the society's own notes, cheque realisation);
- "For <Society>" and the Hon. Secretary / Treasurer / Chairman sign-off.

Payments are acknowledged on separate receipts (receipt_pdf), never on the
bill.

Amounts print as "Rs." — the standard PDF fonts have no rupee glyph.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from xml.sax.saxutils import escape

from app.modules.billing.models.billing import (
    ChargeType, MaintenanceBill, MaintenanceSettings,
)

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#555555")
FRAME = colors.HexColor("#8A8A8A")
ACCENT = colors.HexColor("#0B4A8B")
ZERO = Decimal("0")

_base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=12, textColor=INK)
S = {
    "society": ParagraphStyle("society", parent=_base, fontSize=21, leading=25, alignment=TA_CENTER,
                              textColor=ACCENT),
    "centre": ParagraphStyle("centre", parent=_base, fontSize=10.5, leading=13.5, alignment=TA_CENTER),
    "centre_small": ParagraphStyle("centre_small", parent=_base, fontSize=8.5, alignment=TA_CENTER, textColor=MUTED),
    "cell": _base,
    "cell_b": ParagraphStyle("cell_b", parent=_base, fontName="Helvetica-Bold"),
    "cell_r": ParagraphStyle("cell_r", parent=_base, alignment=TA_RIGHT),
    "cell_rb": ParagraphStyle("cell_rb", parent=_base, fontName="Helvetica-Bold", alignment=TA_RIGHT),
    "cell_c": ParagraphStyle("cell_c", parent=_base, alignment=TA_CENTER),
    "big": ParagraphStyle("big", parent=_base, fontName="Helvetica-Bold", fontSize=12.5, leading=15),
    "head": ParagraphStyle("head", parent=_base, fontSize=10),
    "head_c": ParagraphStyle("head_c", parent=_base, fontSize=10, alignment=TA_CENTER),
    "note": ParagraphStyle("note", parent=_base, fontSize=7.8, leading=9.6),
    "small": ParagraphStyle("small", parent=_base, fontSize=7.5, leading=9.5, textColor=MUTED),
    "small_r": ParagraphStyle("small_r", parent=_base, fontSize=7.5, leading=9.5, alignment=TA_RIGHT),
    "sign": ParagraphStyle("sign", parent=_base, fontSize=8, alignment=TA_CENTER),
}

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


def _p(text, style="cell") -> Paragraph:
    return Paragraph(escape(str(text)) if text is not None else "", S[style])


def member_name(flat, resident=None) -> str:
    """The member a bill or receipt is addressed to: the given resident, else
    the flat's primary owner, else any active resident of the flat."""
    if resident:
        return resident.full_name
    residents = [r for r in (flat.residents if flat else []) if r.is_active]
    residents.sort(key=lambda r: (not r.is_primary, r.resident_type.value not in ("owner", "co_owner")))
    return residents[0].full_name if residents else "-"


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


def _rounded_box(rows, widths, extra=()) -> Table:
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, FRAME),
        ("ROUNDEDCORNERS", [7, 7, 7, 7]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        *extra,
    ]))
    return t


def society_header(society, width) -> Table:
    """The boxed letterhead: name, Regn. No., address, GSTIN/PAN."""
    name = society.name if society else "Society"
    head = [[_p(name.upper(), "society")], [Spacer(1, 2 * mm)]]
    if society and society.registration_number:
        head.append([_p(f"Regn. No. {society.registration_number}", "centre")])
    address = ", ".join(x for x in [
        (society.address or "").strip() if society else "", society.city if society else None,
        society.state if society else None] if x)
    if society and society.pincode:
        address = f"{address} {society.pincode}".strip()
    if address:
        head.append([_p(address.upper() + ".", "centre")])
    ids = []
    if society and society.gst_number:
        ids.append(f"GSTIN: {society.gst_number}")
    if society and society.pan_number:
        ids.append(f"PAN: {society.pan_number}")
    if ids:
        head.append([_p("   |   ".join(ids), "centre_small")])
    return _rounded_box(head, [width], [
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 1),
    ])


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


# ── The bill ──────────────────────────────────────────────────────────────────

def generate_maintenance_bill_pdf(
    bill: MaintenanceBill,
    settings: Optional[MaintenanceSettings] = None,
    *,
    compress: bool = True,
    charge_heads: Sequence[str] = (),
    accumulated_interest: Decimal = ZERO,
) -> bytes:
    """`charge_heads`: the society's charge head names in display order —
    heads this bill doesn't charge print as 0.00. `accumulated_interest`: the
    unpaid interest inside the bill's arrears. Payments are not printed on
    the bill: each has its own receipt (receipt_pdf)."""
    society = bill.society
    society_name = society.name if society else "Society"
    flat = bill.flat
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=8 * mm,
        bottomMargin=8 * mm, title=f"Maintenance Bill {bill.invoice_number}",
        author=society_name, pageCompression=1 if compress else 0,
    )
    width = doc.width
    story: List = []

    story.append(society_header(society, width))
    story.append(Spacer(1, 3 * mm))

    # ── Bill particulars: month, member, flat | bill no., dates, area ──
    gst_charged = (bill.tax_amount or 0) > 0
    status = bill.bill_status.value
    left = [
        [_p(_bill_month(bill), "cell_b"), ""],
        [_p("Name :"), _p(member_name(flat, bill.resident).upper(), "big")],
        [_p("FLAT NO"), _p(flat_label(flat), "big")],
    ]
    if gst_charged:
        left.insert(0, [_p("TAX INVOICE", "cell_b"), ""])
    if status == "cancelled":
        left.append([Paragraph("<font color='#B91C1C'><b>CANCELLED</b></font>", S["cell"]), ""])
    full_width_rows = [0] + ([1] if gst_charged else []) + ([len(left) - 1] if status == "cancelled" else [])
    lt = Table(left, colWidths=[22 * mm, width * 0.58 - 22 * mm])
    lt.setStyle(TableStyle([
        *[("SPAN", (0, r), (1, r)) for r in full_width_rows],
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    area = f"{flat.area_sqft:,.0f}   Sq. Feet" if flat and flat.area_sqft else "-"
    right = [
        [_p("Bill No. :"), _p(bill.invoice_number, "cell_b")],
        [_p("Bill Date :"), _p(_d(bill.bill_date))],
        [_p("Due Date", "cell_b"), _p(_d(bill.due_date), "cell_b")],
        [_p("Area Carpet:"), _p(area)],
    ]
    rt = Table(right, colWidths=[26 * mm, width * 0.42 - 26 * mm])
    rt.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    info = Table([[lt, rt]], colWidths=[width * 0.58, width * 0.42])
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info)
    story.append(Spacer(1, 3 * mm))

    # ── Particulars: every charge head, then the summary ──
    lines = [li for li in bill.line_items if not _is_interest(li)]
    amount_of = (lambda li: li.amount) if gst_charged else (lambda li: li.total)
    rows_heads: List[tuple] = []
    used = set()
    for name in charge_heads:
        matched = [li for li in lines if li.description == name and id(li) not in used]
        used.update(id(li) for li in matched)
        rows_heads.append((name, sum((Decimal(amount_of(li)) for li in matched), ZERO)))
    for li in lines:
        if id(li) not in used:
            rows_heads.append((li.description, Decimal(amount_of(li))))
    if gst_charged:
        rates = {li.tax_percent.normalize() for li in lines if li.tax_amount}
        label = f"GST @ {next(iter(rates)):f}%" if len(rates) == 1 else "GST"
        rows_heads.append((label, sum((Decimal(li.tax_amount) for li in lines), ZERO)))

    total = sum((Decimal(li.total) for li in lines), ZERO)
    interest = sum((Decimal(li.total) for li in bill.line_items if _is_interest(li)), ZERO)
    arrears = Decimal(bill.previous_dues or 0)
    acc_interest = min(max(Decimal(accumulated_interest or 0), ZERO), max(arrears, ZERO))
    principal = arrears - acc_interest
    grand = total + arrears + interest + Decimal(bill.penalty_amount or 0) - Decimal(bill.discount_amount or 0)

    left_w, amt_w = width - 42 * mm, 42 * mm
    words_w = left_w * 0.6
    data = [[_p(" ".join("Particulars"), "head"), "", _p("Amount (in Rs.)", "head_c")]]
    data += [[_p(name), "", _p(_inr(amount), "cell_r")] for name, amount in rows_heads]
    data.append(["", "", ""])  # breathing room above the summary, as on the printed bill
    first_summary = len(data)
    summary = [
        (_p(f"Principal Amount Dues :   {_inr(principal)}"), "Total :", total),
        (_p(f"Accumulated Interest   {_inr(acc_interest)}"), "Arrears / Advance", arrears),
        ("", "Interest on Principal Arrears", interest),
    ]
    if bill.penalty_amount:
        summary.append(("", "Late Fee", Decimal(bill.penalty_amount)))
    if bill.discount_amount:
        summary.append(("", "Less: Discount", -Decimal(bill.discount_amount)))
    for left_cell, label, amount in summary:
        data.append([left_cell, _p(label, "cell_r"), _p(_inr(amount), "cell_r")])
    data.append([_p(rs_in_words(grand)), _p("Grand Total :", "cell_r"), _p(_inr(grand), "cell_rb")])
    pt = Table(data, colWidths=[words_w, left_w - words_w, amt_w], repeatRows=1)
    pt.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ("LINEBEFORE", (2, 0), (2, -1), 1, INK),
        ("LINEABOVE", (0, first_summary), (-1, first_summary), 1, INK),
        *[("SPAN", (0, r), (1, r)) for r in range(0, first_summary)],
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, first_summary - 1), 0.6),
        ("BOTTOMPADDING", (0, 1), (-1, first_summary - 1), 0.6),
        ("TOPPADDING", (0, first_summary), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, first_summary), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
    ]))
    story.append(pt)

    # ── Notes ──
    rate = Decimal(settings.interest_rate_pct) if settings and settings.interest_rate_pct is not None else None
    grace = settings.interest_grace_days if settings else 0
    pay_to = settings.bank_account_name if settings and settings.bank_account_name else society_name
    notes = ["PL. INFORM SOCIETY OFFICE WITHIN 7 DAYS IN CASE OF DISCREPANCY IF ANY."]
    n2 = "PL. MENTION YOUR FLAT NO. AND BILL NO. ON BACKSIDE OF CHQ."
    if rate and rate > 0:
        n2 += (f" INT @{rate.normalize():f}% P.A. WILL BE LEVIED ON UNPAID BILLS AFTER THE DUE DATE"
               + (f" (GRACE PERIOD {grace} DAYS)." if grace else "."))
    notes.append(n2)
    if settings and settings.bank_account_number:
        n3 = f"YOU CAN PAY BILL BY NEFT fvg. {pay_to.upper().rstrip('.')}."
        if settings.bank_name:
            n3 += f" {settings.bank_name.upper()}"
        n3 += f" A/C No.{settings.bank_account_number}"
        if settings.bank_ifsc:
            n3 += f" IFSC :{settings.bank_ifsc}"
        if settings.upi_id:
            n3 += f". UPI ID: {settings.upi_id}"
        notes.append(n3 + ".")
    else:
        notes.append(f"CHEQUE TO BE DRAWN IN FAVOUR OF \"{pay_to.upper()}\"."
                     + (f" UPI ID: {settings.upi_id}." if settings and settings.upi_id else ""))
    if settings and settings.bill_notes:
        notes.extend(line.strip() for line in settings.bill_notes.splitlines() if line.strip())
    notes.append("RECEIPT ARE SUBJECT TO REALISATION OF CHEQUE. IN CASE OF CHEQUE RETURNED UNPAID, "
                 "CHQ RETURNED CHGS. WILL BE LEVIED ON ACTUAL BASIS.")
    note_block = [Spacer(1, 1 * mm), Paragraph("Notes :", S["note"])]
    note_block += [Paragraph(f"{i}. {escape(n)}", S["note"]) for i, n in enumerate(notes, 1)]
    story.append(KeepTogether(note_block))
    story.append(Spacer(1, 2 * mm))

    story.append(KeepTogether([sign_off(society_name, width, "This is a computer-generated bill.")]))

    doc.build(story)
    return buf.getvalue()

