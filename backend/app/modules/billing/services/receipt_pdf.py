"""
The receipt for a payment — a document of its own, never printed on the
maintenance bill. The model bye-laws require the society to issue a receipt
for every amount it receives from a member; a receipt says:

- the society (same letterhead as the bill) and "RECEIPT";
- the receipt number and date;
- received with thanks from <member>, flat;
- the amount in words and in figures;
- how it was paid: cash / cheque no. and bank / UPI or NEFT reference;
- what it was paid towards — "ON BILLING": the bill number, its date and
  month; "ON ACCOUNT": the head it was paid for, to be adjusted against
  the member's bills;
- "Subject to Realisation of Cheque" for cheques;
- "For <Society>" and the Hon. Secretary / Treasurer / Chairman sign-off.

Works for both payment records: PaymentReceipt (always against a bill) and
OnlinePaymentSubmission (the Record Payment form — on bill or on account).
A payment that was later reversed (cheque returned) or rejected prints
marked CANCELLED, with the reason.

Bank reconciliation is an internal step and never delays or changes the
receipt.
"""
from decimal import Decimal
from io import BytesIO
from typing import Optional, Union

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.modules.billing.models.billing import (
    MaintenanceBill, OnlinePaymentSubmission, PaymentMode, PaymentReceipt, ReconciliationStatus,
)
from app.modules.billing.services.bill_pdf import (
    ACCENT, FRAME, MODE_LABEL, S, _bill_month, _d, _inr, _p, flat_label, member_name, rs_in_words, sign_off,
    society_header,
)

Payment = Union[PaymentReceipt, OnlinePaymentSubmission]

_TITLE = ParagraphStyle("receipt", parent=S["cell"], fontName="Helvetica-Bold", fontSize=11,
                        alignment=TA_CENTER, textColor=ACCENT)
_KIND = ParagraphStyle("receipt_kind", parent=S["cell"], fontName="Helvetica-Bold", fontSize=7.5,
                       leading=9, alignment=TA_CENTER, textColor=ACCENT)

def payment_detail(p: Payment) -> str:
    """'Cheque No. 004512, UBI, Dahisar (E)' / 'UPI Ref. 4221…' / 'Cash'.
    The Record Payment form keeps a cheque's number in transaction_ref."""
    mode = MODE_LABEL.get(p.payment_mode, p.payment_mode.value.replace("_", " ").title())
    ref = getattr(p, "cheque_number", None) or p.transaction_ref
    detail = mode
    if ref and p.payment_mode == PaymentMode.CHEQUE:
        detail = f"{mode} No. {ref}"
    elif ref and p.payment_mode != PaymentMode.CASH:
        detail = f"{mode} Ref. {ref}"
    return ", ".join([detail] + ([p.bank_name] if p.bank_name else []))


def _set_off(p: Payment) -> list:
    """[(bill, amount)] a recorded payment was set off against."""
    if isinstance(p, OnlinePaymentSubmission):
        return [(a.bill, a.amount) for a in p.allocations if a.released_at is None and a.bill is not None]
    return [(p.bill, p.amount)] if p.bill is not None else []


def _towards(p: Payment, bill: Optional[MaintenanceBill]) -> str:
    set_off = _set_off(p)
    if len(set_off) == 1 and Decimal(set_off[0][1]) == Decimal(p.amount):
        bill = set_off[0][0]
        return (f"Towards Bill No. {bill.invoice_number} Dated : {_d(bill.bill_date)} "
                f"({_bill_month(bill)})")
    if set_off:
        parts = [f"Bill No. {b.invoice_number} ({_bill_month(b)}) Rs. {_inr(a)}" for b, a in set_off]
        left = Decimal(p.amount) - sum((Decimal(a) for _, a in set_off), Decimal(0))
        text = "Towards " + "; ".join(parts)
        if left > 0:
            text += f"; Advance Rs. {_inr(left)}, to be adjusted against future bills"
        return text + "."
    if bill is not None:
        return (f"Towards Bill No. {bill.invoice_number} Dated : {_d(bill.bill_date)} "
                f"({_bill_month(bill)})")
    if getattr(p, "is_advance", False):
        return "Advance payment, to be adjusted against future bills."
    purpose = getattr(p, "purpose", None)
    head = purpose.value.replace("_", " ").title() if purpose is not None else "Maintenance"
    return f"On Account of {head} Charges, to be adjusted against the member's bills."


def _cancelled(p: Payment) -> Optional[str]:
    if isinstance(p, PaymentReceipt) and p.is_reversed:
        return p.reversed_reason or "Payment reversed"
    if isinstance(p, OnlinePaymentSubmission) and (
            p.status == ReconciliationStatus.REJECTED or not p.is_active):
        return p.review_notes or "Payment rejected"
    return None


def generate_payment_receipt_pdf(p: Payment, *, compress: bool = True) -> bytes:
    set_off = _set_off(p)
    bill = set_off[0][0] if set_off else p.bill
    flat = p.flat or (bill.flat if bill else None)
    society = p.society
    society_name = society.name if society else "Society"
    resident = bill.resident if bill else None

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A5), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=8 * mm,
        bottomMargin=8 * mm, title=f"Receipt {p.receipt_number}", author=society_name,
        pageCompression=1 if compress else 0,
    )
    width = doc.width
    story = [*society_header(society, width), Spacer(1, 3 * mm)]

    kind = "ON BILLING" if bill is not None else "ON ACCOUNT"
    heading = [Paragraph("<u>RECEIPT</u>", _TITLE), Paragraph(escape(kind), _KIND)]
    box_w = 50 * mm  # the column; the boxes sit inside its padding
    flat_box = Table([[_p(flat_label(flat), "cell_c")]], colWidths=[box_w - 16], rowHeights=[9 * mm])
    amt_box = Table([[_p(_inr(p.amount), "cell_rb")]], colWidths=[box_w - 16], rowHeights=[9 * mm])
    for b in (flat_box, amt_box):
        b.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, FRAME), ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    cheque = p.payment_mode == PaymentMode.CHEQUE
    rows = [
        [Paragraph(f"Receipt No.: &nbsp;&nbsp; <b>{escape(p.receipt_number)}</b>", S["cell"]), heading,
         _p(f"Date :   {_d(p.payment_date)}", "cell_r")],
        [Paragraph("Received with thanks from &nbsp;&nbsp; "
                   f"<b>{escape(member_name(flat, resident).upper())}</b>", S["cell"]), "", flat_box],
        [_p(rs_in_words(p.amount)), "", ""],
        [_p(f"Vide Cash/Chq.   {payment_detail(p)}"), _p("Rs.", "small_r"), amt_box],
        [_p(_towards(p, bill)), "", ""],
    ]
    if cheque:
        rows.append(["", "", _p("Subject to Realisation of Cheque", "small_r")])
    t = Table(rows, colWidths=[width - box_w - 30 * mm, 30 * mm, box_w])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, FRAME),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("SPAN", (0, 1), (1, 1)), ("SPAN", (0, 2), (2, 2)), ("SPAN", (0, 4), (2, 4)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
    ]))
    story.append(t)

    cancelled = _cancelled(p)
    if cancelled:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"<font color='#B91C1C'><b>CANCELLED:</b> {escape(cancelled)}</font>", S["cell"]))
    story.append(Spacer(1, 3 * mm))
    story.append(KeepTogether([sign_off(society_name, width, "This is a computer-generated receipt.")]))

    doc.build(story)
    return buf.getvalue()
