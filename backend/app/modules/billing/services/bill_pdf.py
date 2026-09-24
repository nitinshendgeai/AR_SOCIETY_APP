"""One-page A4 PDF for a MaintenanceBill — header, flat details, the line
items copied from the society's charge heads at generation time, and the
paid/outstanding position as of now."""
from datetime import date
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.modules.billing.models.billing import MaintenanceBill


def _money(v) -> str:
    return f"Rs. {v:,.2f}"


def generate_maintenance_bill_pdf(bill: MaintenanceBill, society_name: str) -> bytes:
    buf = BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)
    left, right = 18 * mm, width - 18 * mm

    y = height - 22 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, society_name)
    y -= 7 * mm
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, y, "Maintenance Bill")
    c.setFillColor(colors.black)
    y -= 5 * mm
    c.line(left, y, right, y)
    y -= 10 * mm

    flat = bill.flat
    wing_name = flat.wing.name if flat and flat.wing else ""
    flat_number = flat.flat_number if flat else ""
    resident_name = bill.resident.full_name if bill.resident else "-"
    cycle_name = bill.cycle.name if bill.cycle else "-"

    def pair(label_l, value_l, label_r, value_r):
        nonlocal y
        c.setFont("Helvetica-Bold", 9); c.drawString(left, y, label_l)
        c.setFont("Helvetica", 9);      c.drawString(left + 28 * mm, y, value_l)
        c.setFont("Helvetica-Bold", 9); c.drawString(width / 2 + 5 * mm, y, label_r)
        c.setFont("Helvetica", 9);      c.drawString(width / 2 + 30 * mm, y, value_r)
        y -= 6.5 * mm

    pair("Bill No:", bill.invoice_number, "Bill Date:", bill.bill_date.strftime("%d %b %Y"))
    pair("Flat:", f"{wing_name} / {flat_number}", "Due Date:", bill.due_date.strftime("%d %b %Y"))
    pair("Resident:", resident_name[:40], "Period:", cycle_name[:40])
    y -= 4 * mm

    cols = [left, left + 95 * mm, left + 120 * mm, left + 145 * mm]
    c.setFillColor(colors.HexColor("#F2F4F7"))
    c.rect(left, y - 2.5 * mm, right - left, 8 * mm, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols[0] + 2 * mm, y, "Particulars")
    c.drawRightString(cols[1] + 20 * mm, y, "Amount")
    c.drawRightString(cols[2] + 20 * mm, y, "Tax")
    c.drawRightString(right - 2 * mm, y, "Total")
    y -= 9 * mm

    c.setFont("Helvetica", 9)
    for item in bill.line_items:
        c.drawString(cols[0] + 2 * mm, y, item.description[:55])
        c.drawRightString(cols[1] + 20 * mm, y, f"{item.amount:,.2f}")
        c.drawRightString(cols[2] + 20 * mm, y, f"{item.tax_amount:,.2f}")
        c.drawRightString(right - 2 * mm, y, f"{item.total:,.2f}")
        y -= 6.5 * mm

    y -= 1 * mm
    c.line(left, y, right, y)
    y -= 7 * mm

    def total_row(label, value, bold=False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if bold else 9)
        c.drawRightString(cols[2] + 20 * mm, y, label)
        c.drawRightString(right - 2 * mm, y, _money(value))
        y -= 6.5 * mm

    total_row("Subtotal", bill.subtotal)
    if bill.tax_amount:
        total_row("Tax", bill.tax_amount)
    if bill.penalty_amount:
        total_row("Late Fee", bill.penalty_amount)
    if bill.discount_amount:
        total_row("Discount", -bill.discount_amount)
    total_row("Bill Total", bill.total_amount + bill.penalty_amount - bill.discount_amount, bold=True)
    total_row("Paid", bill.paid_amount)
    total_row("Balance Due", bill.outstanding, bold=True)

    y -= 6 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.grey)
    status = bill.bill_status.value.replace("_", " ").title()
    if bill.outstanding > 0 and bill.due_date < date.today() and bill.bill_status.value != "cancelled":
        status = "Overdue"
    c.drawString(left, y, f"Status: {status}")
    y -= 4.5 * mm
    c.drawString(left, y, "Please pay by the due date to avoid late fees. "
                          "This is a computer-generated bill and does not need a signature.")

    c.showPage()
    c.save()
    return buf.getvalue()
