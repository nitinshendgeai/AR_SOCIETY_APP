"""A4 PDF for a MaintenanceBill, laid out the way a co-operative housing
society's maintenance bill is expected to read (Maharashtra model bye-laws:
charges under the heads of bye-law 65-67, interest on arrears, arrears shown
on the bill):

- the society's identity: name, registration number, address, GSTIN/PAN;
- the member and flat, bill number, bill date, billing period, due date;
- the charges head by head (with GST when it applies), arrears as on the
  bill date and the total payable, also in words;
- payments received against the bill so far, and the balance;
- where to pay (the society's bank account / UPI, when configured);
- the notes the bye-laws require members to be told — pay by the due date,
  simple interest on late payment at the society's rate — and a sign-off
  for the Hon. Secretary / Treasurer.

Amounts print as "Rs." — the standard PDF fonts have no rupee glyph.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import List, Optional

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
    MaintenanceBill, MaintenanceSettings, ReconciliationStatus,
)

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
RULE = colors.HexColor("#D1D5DB")
BAND = colors.HexColor("#F3F4F6")
ACCENT = colors.HexColor("#1F3A8A")

_base = ParagraphStyle("base", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK)
S = {
    "society": ParagraphStyle("society", parent=_base, fontName="Helvetica-Bold", fontSize=15,
                              leading=18, alignment=TA_CENTER, textColor=ACCENT),
    "centre": ParagraphStyle("centre", parent=_base, alignment=TA_CENTER, textColor=MUTED),
    "title": ParagraphStyle("title", parent=_base, fontName="Helvetica-Bold", fontSize=11,
                            alignment=TA_CENTER, textColor=colors.white),
    "label": ParagraphStyle("label", parent=_base, textColor=MUTED),
    "value": ParagraphStyle("value", parent=_base, fontName="Helvetica-Bold"),
    "cell": _base,
    "cell_r": ParagraphStyle("cell_r", parent=_base, alignment=TA_RIGHT),
    "head": ParagraphStyle("head", parent=_base, fontName="Helvetica-Bold"),
    "head_r": ParagraphStyle("head_r", parent=_base, fontName="Helvetica-Bold", alignment=TA_RIGHT),
    "section": ParagraphStyle("section", parent=_base, fontName="Helvetica-Bold", fontSize=9.5,
                              spaceBefore=4, spaceAfter=3),
    "note": ParagraphStyle("note", parent=_base, fontSize=8, leading=10.5),
    "small": ParagraphStyle("small", parent=_base, fontSize=7.5, textColor=MUTED),
    "sign": ParagraphStyle("sign", parent=_base, alignment=TA_RIGHT),
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


def _rs(v) -> str:
    return f"Rs. {_inr(v)}"


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


def amount_in_words(v) -> str:
    """Rs. 6,815.46 → 'Rupees Six Thousand Eight Hundred Fifteen and Paise Forty Six Only'."""
    v = abs(Decimal(v or 0)).quantize(Decimal("0.01"))
    rupees, paise = int(v), int((v - int(v)) * 100)
    words = f"Rupees {_indian_words(rupees)}"
    if paise:
        words += f" and Paise {_indian_words(paise)}"
    return words + " Only"


def _d(value: Optional[date]) -> str:
    return value.strftime("%d %b %Y") if value else "-"


def _p(text, style="cell") -> Paragraph:
    return Paragraph(escape(str(text)) if text is not None else "", S[style])


def _member_name(bill: MaintenanceBill) -> str:
    """The member the bill is addressed to: the resident it was raised for,
    else the flat's primary owner, else any active resident of the flat."""
    if bill.resident:
        return bill.resident.full_name
    residents = [r for r in (bill.flat.residents if bill.flat else []) if r.is_active]
    residents.sort(key=lambda r: (not r.is_primary, r.resident_type.value not in ("owner", "co_owner")))
    return residents[0].full_name if residents else "-"


# ── The bill ──────────────────────────────────────────────────────────────────

def generate_maintenance_bill_pdf(bill: MaintenanceBill, settings: Optional[MaintenanceSettings] = None,
                                  *, compress: bool = True) -> bytes:
    society = bill.society
    flat = bill.flat
    cycle = bill.cycle
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm,
        bottomMargin=12 * mm, title=f"Maintenance Bill {bill.invoice_number}",
        author=society.name if society else "", pageCompression=1 if compress else 0,
    )
    width = doc.width
    story: List = []

    # Society header
    story.append(Paragraph(escape(society.name if society else "Society"), S["society"]))
    if society and society.registration_number:
        story.append(Paragraph(escape(f"Regn. No.: {society.registration_number}"), S["centre"]))
    address = ", ".join(x for x in [
        (society.address or "").strip() if society else "", society.city if society else None,
        society.state if society else None, society.pincode if society else None] if x)
    if address:
        story.append(Paragraph(escape(address), S["centre"]))
    tax_ids = []
    if society and society.gst_number:
        tax_ids.append(f"GSTIN: {society.gst_number}")
    if society and society.pan_number:
        tax_ids.append(f"PAN: {society.pan_number}")
    contact = []
    if society and society.contact_phone:
        contact.append(f"Ph: {society.contact_phone}")
    if society and society.contact_email:
        contact.append(f"Email: {society.contact_email}")
    for line in (tax_ids, contact):
        if line:
            story.append(Paragraph(escape("   |   ".join(line)), S["centre"]))
    story.append(Spacer(1, 3 * mm))

    # Title band (tax invoice when GST was charged; status stamp when settled)
    gst_charged = (bill.tax_amount or 0) > 0
    title = "MAINTENANCE BILL" + (" / TAX INVOICE" if gst_charged else "")
    status = bill.bill_status.value
    stamp = {"paid": "PAID", "cancelled": "CANCELLED"}.get(status, "")
    band = Table([[Paragraph(title, S["title"])]], colWidths=[width])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(band)
    story.append(Spacer(1, 3 * mm))

    # Member / bill details
    wing = flat.wing.name if flat and flat.wing else ""
    flat_label = f"{wing} - {flat.flat_number}" if flat and wing else (flat.flat_number if flat else "-")
    area = f"{flat.area_sqft:,.0f} sq ft" if flat and flat.area_sqft else "-"
    period = f"{_d(cycle.cycle_start)} to {_d(cycle.cycle_end)}" if cycle else "-"
    member = _member_name(bill)
    details = [
        [_p("Member Name", "label"), _p(member, "value"), _p("Bill No.", "label"), _p(bill.invoice_number, "value")],
        [_p("Flat No.", "label"), _p(flat_label, "value"), _p("Bill Date", "label"), _p(_d(bill.bill_date), "value")],
        [_p("Area", "label"), _p(area, "value"), _p("Billing Period", "label"), _p(period, "value")],
        [_p("Bill For", "label"), _p(cycle.name if cycle else "-", "value"),
         _p("Due Date", "label"), _p(_d(bill.due_date), "value")],
    ]
    t = Table(details, colWidths=[26 * mm, width / 2 - 26 * mm, 26 * mm, width / 2 - 26 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEAFTER", (1, 0), (1, -1), 0.6, RULE),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    # Charges
    items = list(bill.line_items)
    if gst_charged:
        head = [_p("Sr.", "head"), _p("Particulars", "head"), _p("Amount", "head_r"),
                _p("GST", "head_r"), _p("Total (Rs.)", "head_r")]
        widths = [10 * mm, width - 10 * mm - 3 * 28 * mm, 28 * mm, 28 * mm, 28 * mm]
        rows = [[_p(i), _p(li.description), _p(_inr(li.amount), "cell_r"),
                 _p(_inr(li.tax_amount), "cell_r"), _p(_inr(li.total), "cell_r")]
                for i, li in enumerate(items, 1)]
    else:
        head = [_p("Sr.", "head"), _p("Particulars", "head"), _p("Amount (Rs.)", "head_r")]
        widths = [10 * mm, width - 10 * mm - 34 * mm, 34 * mm]
        rows = [[_p(i), _p(li.description), _p(_inr(li.total), "cell_r")] for i, li in enumerate(items, 1)]
    charges = Table([head] + rows, colWidths=widths, repeatRows=1)
    charges.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(charges)
    story.append(Spacer(1, 2 * mm))

    # Totals: this bill, arrears as on the bill date, total payable
    current = Decimal(bill.total_amount or 0)
    adjustments = Decimal(bill.penalty_amount or 0) - Decimal(bill.discount_amount or 0)
    previous = Decimal(bill.previous_dues or 0)
    payable = current + adjustments + previous
    totals = [["Current bill charges", _rs(current)]]
    if gst_charged:
        totals.insert(0, ["of which GST", _rs(bill.tax_amount)])
    if bill.penalty_amount:
        totals.append(["Add: Late fee", _rs(bill.penalty_amount)])
    if bill.discount_amount:
        totals.append(["Less: Discount", _rs(-Decimal(bill.discount_amount))])
    totals.append([f"Add: Arrears as on {_d(bill.bill_date)}", _rs(previous)])
    totals.append(["Total amount payable", _rs(payable)])
    tt = Table([[_p(a, "cell_r"), _p(b, "cell_r")] for a, b in totals[:-1]]
               + [[_p(totals[-1][0], "head_r"), _p(totals[-1][1], "head_r")]],
               colWidths=[width - 38 * mm, 38 * mm])
    tt.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("BACKGROUND", (0, -1), (-1, -1), BAND),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tt)
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"<b>Amount in words:</b> {escape(amount_in_words(payable))}", S["cell"]))
    story.append(Spacer(1, 4 * mm))

    # Payments received against this bill (live), and what's left of it
    # Payments land in two tables (PaymentReceipt, and on-bill
    # OnlinePaymentSubmission from the Record Payment form); both count
    # towards paid_amount, so list both — as the bill detail screen does.
    receipts = [r for r in bill.receipts if not r.is_reversed] + [
        s for s in bill.online_payments
        if s.is_active and s.status != ReconciliationStatus.REJECTED]
    if receipts or status != "draft":
        block = [Paragraph("Payments received against this bill", S["section"])]
        if receipts:
            rrows = [[_p("Receipt No.", "head"), _p("Date", "head"), _p("Mode", "head"),
                      _p("Reference", "head"), _p("Amount (Rs.)", "head_r")]]
            for r in sorted(receipts, key=lambda r: r.payment_date):
                ref = r.transaction_ref or getattr(r, "cheque_number", None) or ""
                rrows.append([_p(r.receipt_number), _p(_d(r.payment_date)),
                              _p(r.payment_mode.value.replace("_", " ").title()), _p(ref),
                              _p(_inr(r.amount), "cell_r")])
            rt = Table(rrows, colWidths=[32 * mm, 26 * mm, 28 * mm, width - 120 * mm, 34 * mm])
            rt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]))
            block.append(rt)
        else:
            block.append(Paragraph("None yet.", S["small"]))
        balance = Decimal(bill.outstanding or 0)
        block.append(Spacer(1, 1.5 * mm))
        block.append(Paragraph(
            f"Paid so far: <b>{_rs(bill.paid_amount)}</b> &nbsp;&nbsp; Balance of this bill: <b>{_rs(balance)}</b>"
            + (f" &nbsp;&nbsp; <font color='#15803D'><b>{stamp}</b></font>" if stamp == "PAID" else "")
            + (f" &nbsp;&nbsp; <font color='#B91C1C'><b>{stamp}</b></font>" if stamp == "CANCELLED" else ""),
            S["cell"]))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 4 * mm))

    # Where to pay
    pay_to = settings.bank_account_name if settings and settings.bank_account_name else (society.name if society else "")
    bank_rows = []
    if settings:
        for label, value in (("Account Name", pay_to if settings.bank_account_number else None),
                             ("Bank", settings.bank_name), ("Account No.", settings.bank_account_number),
                             ("IFSC", settings.bank_ifsc), ("UPI ID", settings.upi_id)):
            if value:
                bank_rows.append([_p(label, "label"), _p(value, "value")])
    if bank_rows:
        bt = Table(bank_rows, colWidths=[30 * mm, width - 30 * mm])
        bt.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, RULE), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(KeepTogether([Paragraph("Payment details", S["section"]), bt]))
        story.append(Spacer(1, 4 * mm))

    # Notes members must be told (bye-laws), plus the society's own
    rate = Decimal(settings.interest_rate_pct) if settings and settings.interest_rate_pct is not None else None
    grace = settings.interest_grace_days if settings else 0
    notes = [f"Please pay the total amount payable on or before the due date, {_d(bill.due_date)}."]
    if rate and rate > 0:
        notes.append(
            f"Simple interest at {rate.normalize():f}% per annum is charged on amounts not paid by the due date"
            + (f" (after a grace period of {grace} days)" if grace else "")
            + ", as provided in the society's bye-laws.")
    notes.append(f"Pay by cheque / NEFT / UPI in favour of \"{pay_to}\". "
                 "Please mention your flat number and bill number with the payment; "
                 "a receipt is issued for every payment.")
    notes.append("Please bring any discrepancy in this bill to the notice of the Secretary / Managing Committee.")
    if settings and settings.bill_notes:
        notes.extend(line.strip() for line in settings.bill_notes.splitlines() if line.strip())
    note_block = [Paragraph("Notes", S["section"])]
    note_block += [Paragraph(f"{i}. {escape(n)}", S["note"]) for i, n in enumerate(notes, 1)]
    note_block.append(Paragraph("E. &amp; O. E.", S["small"]))
    story.append(KeepTogether(note_block))
    story.append(Spacer(1, 8 * mm))

    story.append(KeepTogether([
        Paragraph(f"For <b>{escape(society.name if society else 'the Society')}</b>", S["sign"]),
        Spacer(1, 10 * mm),
        Paragraph("Hon. Secretary / Treasurer", S["sign"]),
        Spacer(1, 4 * mm),
        Paragraph("This is a computer-generated bill and does not require a signature.", S["small"]),
    ]))

    doc.build(story)
    return buf.getvalue()
