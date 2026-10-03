"""The work order the society hands the vendor: the letterhead, the order's
number and date, the vendor, what is to be done and for how much (in words),
the quotation and the resolutions it rests on, the terms (dates, advance,
retention, defect liability, payment), the usual conditions, and signatures
of the Hon. Secretary and Chairman with the vendor's acceptance."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, _inr, amount_in_words, society_header
from app.modules.billing.services.defaulters_pdf import long_date
from app.modules.vendor.models.vendor import SanctionLevel

P = {
    "title": ParagraphStyle("wo_title", parent=S["title"], fontSize=13, leading=16),
    "body": ParagraphStyle("wo_body", parent=S["cell"], fontSize=9.2, leading=12.2),
    "bold": ParagraphStyle("wo_bold", parent=S["cell_b"], fontSize=9.2, leading=13),
    "label": ParagraphStyle("wo_label", parent=S["cell"], fontSize=8.5, leading=11, textColor=MUTED),
    "right": ParagraphStyle("wo_right", parent=S["cell_r"], fontSize=9.2, leading=13),
    "right_b": ParagraphStyle("wo_right_b", parent=S["cell_rb"], fontSize=9.2, leading=13),
    "small": ParagraphStyle("wo_small", parent=S["cell"], fontSize=8.2, leading=10.4),
    "sign": ParagraphStyle("wo_sign", parent=S["sign"], fontSize=8.5),
}

CONDITIONS = [
    "The work shall be carried out as per the scope above and the quotation accepted, under the supervision of "
    "the society's representative, and to the satisfaction of the Managing Committee.",
    "The contractor shall employ competent workers, follow all safety precautions and be solely responsible for "
    "their wages, insurance and any injury or accident during the work.",
    "Any damage to the society's or members' property during the work shall be made good by the contractor at "
    "their cost.",
    "No extra or additional work shall be done without a written order of the society; work beyond the "
    "sanctioned amount will not be paid unless sanctioned in advance.",
    "Payment will be released against the contractor's bill after the Managing Committee certifies completion, "
    "less any retention and taxes deductible at source as per law.",
]


def _p(text, style="body"):
    return Paragraph(escape(str(text or "")), P[style])


def _d(d):
    return f"{d:%d-%m-%Y}" if d else "—"


def render_work_order_pdf(wo, society, *, compress: bool = True) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=8 * mm,
                            bottomMargin=12 * mm, title=f"Work Order {wo.wo_number}", author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    v = wo.vendor
    story = [*society_header(society, width), Spacer(1, 3.5 * mm), Paragraph("WORK ORDER", P["title"]),
             Spacer(1, 2 * mm)]

    head = Table([[_p(f"No. {wo.wo_number}", "bold"), _p(f"Date: {long_date(wo.issued_on or wo.sanctioned_at.date())}",
                                                          "right")]],
                 colWidths=[width / 2, width / 2])
    story += [head, Spacer(1, 2 * mm)]

    to = ["To,", v.company_name if v else ""]
    if v and v.contact_person:
        to.append(f"Kind attn.: {v.contact_person}")
    if v and v.address:
        to.append(", ".join(x for x in [v.address, v.city, v.pincode] if x))
    ids = [f"GSTIN: {v.gst_number}" if v and v.gst_number else "", f"PAN: {v.pan_number}" if v and v.pan_number else ""]
    if any(ids):
        to.append("   ".join(x for x in ids if x))
    if v:
        to.append(f"Mobile: {v.mobile}  ·  Vendor code: {v.vendor_code}")
    story += [_p(line, "bold" if i == 1 else "body") for i, line in enumerate(to)]
    story.append(Spacer(1, 3 * mm))
    story.append(_p(f"Subject: {wo.title}" + (f" at {wo.location}" if wo.location else ""), "bold"))
    story.append(Spacer(1, 2 * mm))

    chosen = next((q for q in wo.quotations if q.is_active and q.is_selected), None)
    refs = []
    if chosen:
        refs.append(f"Your quotation{' No. ' + chosen.quotation_ref if chosen.quotation_ref else ''} dated "
                    f"{_d(chosen.quotation_date)}")
    refs.append(f"Managing Committee resolution No. {wo.committee_resolution_no} dated {_d(wo.committee_meeting_date)}")
    if wo.sanction_level == SanctionLevel.GENERAL_BODY and wo.gb_resolution_no:
        refs.append(f"General Body resolution No. {wo.gb_resolution_no} dated {_d(wo.gb_meeting_date)}")
    story.append(_p("Ref.: " + "; ".join(refs) + ".", "small"))
    story.append(Spacer(1, 3 * mm))
    story.append(_p("Dear Sir/Madam,"))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_p("With reference to the above, the society is pleased to award you the following work on the "
                    "terms and conditions set out below. Please sign and return a copy of this order as your "
                    "acceptance."))
    story.append(Spacer(1, 3 * mm))

    if wo.scope_of_work:
        story.append(_p("Scope of work", "bold"))
        for line in wo.scope_of_work.splitlines():
            if line.strip():
                story.append(_p(line.strip()))
        story.append(Spacer(1, 3 * mm))

    amount = chosen.amount if chosen else wo.sanctioned_amount
    gst = chosen.gst_amount if chosen else 0
    rows = [[_p("Work order value", "bold"), _p("Rs.", "right_b")],
            [_p("Amount"), _p(_inr(amount), "right")],
            [_p("GST"), _p(_inr(gst), "right")],
            [_p("Total sanctioned", "bold"), _p(_inr(wo.sanctioned_amount), "right_b")]]
    t = Table(rows, colWidths=[width - 45 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK), ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    story += [t, Spacer(1, 1 * mm), _p(f"({amount_in_words(wo.sanctioned_amount)})", "small"), Spacer(1, 3 * mm)]

    terms = [
        ("Start of work", _d(wo.start_date)),
        ("To be completed by", _d(wo.due_date)),
        ("Advance", f"Rs. {_inr(wo.advance_amount)}" if wo.advance_amount else "Nil"),
        ("Retention", f"{wo.retention_pct:g}% of the bill value, released after the defect liability period"
         if wo.retention_pct else "Nil"),
        ("Defect liability period", f"{wo.defect_liability_months} months from completion"
         if wo.defect_liability_months else "Nil"),
        ("Payment terms", wo.payment_terms or "After completion is certified by the Managing Committee"),
    ]
    tt = Table([[_p(k, "label"), _p(val)] for k, val in terms], colWidths=[48 * mm, width - 48 * mm])
    tt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING", (0, 0), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8)]))
    story += [_p("Terms", "bold"), tt, Spacer(1, 2.5 * mm), _p("Conditions", "bold")]
    for i, c in enumerate(CONDITIONS, 1):
        story.append(_p(f"{i}. {c}", "small"))
    story.append(Spacer(1, 6 * mm))
    col = width / 3
    signs = Table([
        [_p(f"For {name.upper()}", "sign"), "", ""],
        [Spacer(1, 9 * mm), "", ""],
        [_p("Hon. Secretary", "sign"), _p("Chairman", "sign"), _p("Accepted by the contractor", "sign")],
    ], colWidths=[col] * 3)
    signs.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("LINEABOVE", (0, 2), (0, 2), 0.8, INK), ("LINEABOVE", (1, 2), (1, 2), 0.8, INK),
        ("LINEABOVE", (2, 2), (2, 2), 0.8, INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(KeepTogether([signs]))

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 7 * mm, f"{name} · Work Order {wo.wo_number}")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 7 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
