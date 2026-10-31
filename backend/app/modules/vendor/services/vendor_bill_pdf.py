"""A vendor's bill as the society holds it: the letterhead, the vendor, the bill's number and dates, the amount with
its GST, the TDS held and the net payable (in words), the payments made on it, and signature lines for whoever
prepared, checked and approved it (Hon. Treasurer and Chairman). A cancelled bill prints marked CANCELLED."""
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import List
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.accounts.services.documents_pdf import _signature_boxes
from app.modules.billing.services.bill_pdf import (
    BAND, INK, MUTED, RULE, S, _dm, _inr, amount_in_words, society_header,
)

P = {
    "title": ParagraphStyle("vb_title", parent=S["title"], fontSize=13, leading=16),
    "body": ParagraphStyle("vb_body", parent=S["cell"], fontSize=9.2, leading=12.2),
    "bold": ParagraphStyle("vb_bold", parent=S["cell_b"], fontSize=9.2, leading=12.2),
    "label": ParagraphStyle("vb_label", parent=S["cell"], fontSize=8.5, leading=11, textColor=MUTED),
    "right": ParagraphStyle("vb_right", parent=S["cell_r"], fontSize=9.2, leading=12.2),
    "right_b": ParagraphStyle("vb_right_b", parent=S["cell_rb"], fontSize=9.2, leading=12.2),
    "th": ParagraphStyle("vb_th", parent=S["cell_b"], fontSize=8.5, leading=10.5),
    "th_r": ParagraphStyle("vb_th_r", parent=S["cell_rb"], fontSize=8.5, leading=10.5),
    "td": ParagraphStyle("vb_td", parent=S["cell"], fontSize=8.5, leading=10.5),
    "td_r": ParagraphStyle("vb_td_r", parent=S["cell_r"], fontSize=8.5, leading=10.5),
}

ZERO = Decimal("0")


def _p(text, style="body") -> Paragraph:
    return Paragraph(escape(str(text if text is not None else "")), P[style])


def _money(v) -> Decimal:
    return Decimal(v or 0)


def _mode(m) -> str:
    return m.value.replace("_", " ").title() if m is not None else "-"


def _kv(rows, widths) -> Table:
    t = Table([[_p(k, "label"), _p(v)] for k, v in rows if v], colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8)]))
    return t


def render_vendor_bill_pdf(inv, society, *, compress: bool = True) -> bytes:
    """`inv`: a VendorInvoice; `society`: its Society."""
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=8 * mm,
                            bottomMargin=12 * mm, title=f"Vendor Bill {inv.invoice_number}", author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    v = inv.vendor
    story: List = [*society_header(society, width), Spacer(1, 3.5 * mm), Paragraph("VENDOR BILL", P["title"])]
    if not inv.is_active:
        story.append(Paragraph("<font color='#B91C1C'><b>CANCELLED</b></font>", S["cell_c"]))
    story.append(Spacer(1, 3 * mm))

    # ── Vendor and bill details ──
    address = ", ".join(x for x in [v.address, v.city, v.pincode] if x) if v else ""
    bank = ", ".join(x for x in [v.bank_name, f"A/c {v.bank_account}" if v.bank_account else "",
                                 f"IFSC {v.bank_ifsc}" if v.bank_ifsc else ""] if x) if v else ""
    half = width / 2
    left = _kv([("Vendor", v.company_name if v else ""), ("Address", address),
                ("GSTIN", v.gst_number if v else ""), ("PAN", v.pan_number if v else ""),
                ("Contact", ", ".join(x for x in [v.contact_person, v.mobile] if x) if v else ""),
                ("Bank", bank), ("Vendor code", v.vendor_code if v else "")], [20 * mm, half - 24 * mm])
    right = _kv([("Bill No.", inv.invoice_number), ("Bill Date", _dm(inv.invoice_date)),
                 ("Due Date", _dm(inv.due_date) if inv.due_date else ""),
                 ("Work Order", inv.work_order.wo_number if inv.work_order else "")], [22 * mm, half - 26 * mm])
    box = Table([[left, right]], colWidths=[half, half])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [box, Spacer(1, 3 * mm)]
    if inv.description:
        story += [_p(f"Particulars: {inv.description}"), Spacer(1, 3 * mm)]

    # ── Amounts ──
    total, tds = _money(inv.total_amount), _money(inv.tds_amount)
    net = total - tds                      # as the app's own outstanding: the bill less the TDS held
    paid = _money(inv.paid_amount)
    rows = [[_p("Particulars", "th"), _p("Rs.", "th_r")], [_p("Bill amount (before GST)"), _p(_inr(inv.amount), "right")]]
    for label, value in (("CGST", inv.cgst_amount), ("SGST", inv.sgst_amount), ("IGST", inv.igst_amount)):
        if _money(value) > 0:
            rows.append([_p(label), _p(_inr(value), "right")])
    if _money(inv.gst_amount) > 0 and not any(_money(x) > 0 for x in (inv.cgst_amount, inv.sgst_amount, inv.igst_amount)):
        rows.append([_p("GST"), _p(_inr(inv.gst_amount), "right")])
    rows.append([_p("Total bill amount", "bold"), _p(_inr(total), "right_b")])
    if tds > 0:
        section = f" u/s {inv.tds_section}" if inv.tds_section else ""
        rate = f" @ {Decimal(inv.tds_rate or 0).normalize():f}%" if _money(inv.tds_rate) > 0 else ""
        rows.append([_p(f"Less: TDS{section}{rate}"), _p(_inr(-tds), "right")])
    rows += [[_p("Net payable to the vendor", "bold"), _p(_inr(net), "right_b")],
             [_p("Paid so far"), _p(_inr(paid), "right")],
             [_p("Balance to be paid", "bold"), _p(_inr(max(net - paid, ZERO)), "right_b")]]
    t = Table(rows, colWidths=[width - 45 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK), ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
    ]))
    story += [t, Spacer(1, 1.5 * mm), _p(f"Net payable in words: {amount_in_words(net)}", "bold"), Spacer(1, 4 * mm)]

    # ── Payments made ──
    if inv.payments:
        head = ["Payment No.", "Date", "Mode", "Reference / Bank", "Amount", "TDS", "Paid to vendor"]
        pay = [[_p(h, "th_r" if i >= 4 else "th") for i, h in enumerate(head)]]
        for p in inv.payments:
            ref = ", ".join(x for x in [p.transaction_ref, p.bank_name] if x)
            tag = " (reversed)" if p.is_reversed else ""
            pay.append([_p(p.payment_number + tag, "td"), _p(_dm(p.payment_date), "td"), _p(_mode(p.payment_mode), "td"),
                        _p(ref, "td"), _p(_inr(p.amount), "td_r"), _p(_inr(p.tds_amount), "td_r"),
                        _p(_inr(_money(p.amount) - _money(p.tds_amount)), "td_r")])
        widths = [34 * mm, 21 * mm, 17 * mm, 0, 22 * mm, 16 * mm, 22 * mm]
        widths[3] = width - sum(widths)
        pt = Table(pay, colWidths=widths, repeatRows=1)
        pt.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, INK), ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
            ("BACKGROUND", (0, 0), (-1, 0), BAND), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ]))
        story += [_p("Payments made", "bold"), Spacer(1, 1 * mm), pt, Spacer(1, 4 * mm)]
    else:
        story += [_p("No payment has been made on this bill yet."), Spacer(1, 4 * mm)]

    story += [Spacer(1, 6 * mm),
              KeepTogether([_signature_boxes(["Prepared by", "Checked by", "Hon. Treasurer", "Chairman"],
                                             [""] * 4, width)])]

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 7 * mm, f"{name} · Vendor Bill {inv.invoice_number}")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 7 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
