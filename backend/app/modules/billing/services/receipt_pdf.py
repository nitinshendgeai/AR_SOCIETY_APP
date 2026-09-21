"""
Simple one-page PDF receipt for an OnlinePaymentSubmission.

Deliberately minimal — a plain, readable receipt confirming what the FMC
Manager recorded, not a finance-grade invoice. Good enough to hand a
resident proof of the entry while the reconciliation status is worked out.
"""
from io import BytesIO
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.modules.billing.models.billing import OnlinePaymentSubmission


def generate_online_payment_receipt_pdf(submission: OnlinePaymentSubmission, society_name: str) -> bytes:
    buf = BytesIO()
    width, height = A5
    c = canvas.Canvas(buf, pagesize=A5)

    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, society_name)
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, y, "Payment Acknowledgement Receipt")
    c.setFillColor(colors.black)
    y -= 4 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 10 * mm

    def row(label: str, value: str):
        nonlocal y
        c.setFont("Helvetica-Bold", 9)
        c.drawString(15 * mm, y, label)
        c.setFont("Helvetica", 9)
        c.drawString(60 * mm, y, value)
        y -= 7 * mm

    row("Receipt No:", submission.receipt_number)
    row("Flat:", f"{submission.wing.name if submission.wing else ''} / {submission.flat.flat_number if submission.flat else ''}")
    row("Amount:", f"Rs. {submission.amount}")
    row("Payment Date:", submission.payment_date.isoformat())
    row("Payment Mode:", submission.payment_mode.value.replace("_", " ").title())
    row("Transaction Ref:", submission.transaction_ref or "-")
    row("Bank:", submission.bank_name or "-")
    row("Status:", submission.status.value.replace("_", " ").title())
    if submission.notes:
        row("Notes:", submission.notes[:60])

    y -= 5 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 8 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.grey)
    c.drawString(15 * mm, y, "This receipt acknowledges the payment screenshot submitted for bank")
    y -= 4.5 * mm
    c.drawString(15 * mm, y, "reconciliation. It is not proof of final reconciliation against the bank statement.")

    c.showPage()
    c.save()
    return buf.getvalue()
