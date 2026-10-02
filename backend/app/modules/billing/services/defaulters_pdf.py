"""
The list of defaulters as the committee puts it up for the general body:
the society's letterhead, "List of Defaulters as on <date>", one line per
flat with its dues aged by how long they have been outstanding, totals, the
interest note and the Hon. Secretary's signature.
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, _inr, society_header


def long_date(d: date) -> str:
    """'2nd October 2026'."""
    n = d.day
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix} {d:%B %Y}"

_b = S["cell"]
P = {
    "title": ParagraphStyle("df_title", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("df_sub", parent=S["centre_small"], fontSize=8.5),
    "th": ParagraphStyle("df_th", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5),
    "th_r": ParagraphStyle("df_th_r", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5, alignment=2),
    "td": ParagraphStyle("df_td", parent=_b, fontSize=8, leading=9.8),
    "td_r": ParagraphStyle("df_td_r", parent=_b, fontSize=8, leading=9.8, alignment=2),
    "td_rb": ParagraphStyle("df_td_rb", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.8, alignment=2),
    "note": ParagraphStyle("df_note", parent=_b, fontSize=7.8, leading=10, textColor=MUTED),
    "sign": ParagraphStyle("df_sign", parent=S["sign"], fontSize=8),
}


def _m(v) -> str:
    return "" if not v or Decimal(v) == 0 else _inr(v)


def _p(text, style) -> Paragraph:
    return Paragraph(escape(str(text or "")), P[style])


def render_defaulters_pdf(data: dict, society, *, compress: bool = True) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=8 * mm, bottomMargin=12 * mm, title="List of Defaulters", author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    s = data["summary"]
    as_of = date.fromisoformat(s["as_of"])
    heading = ("LIST OF DEFAULTERS" if not s["include_all"] else "MEMBERS' DUES OUTSTANDING") + \
        f" AS ON {long_date(as_of).upper()}"
    sub = (f"Members with maintenance dues outstanding for more than {s['min_months']} months after the due date"
           if not s["include_all"] else "Every flat with maintenance dues outstanding, aged from the due date")
    story = [*society_header(society, width), Spacer(1, 4 * mm), Paragraph(escape(heading), P["title"]),
             Paragraph(escape(sub), P["sub"]), Spacer(1, 3 * mm)]

    buckets = [b for b in s["buckets"] if b["key"] != "not_due"]
    head = ([_p("Sr.", "th"), _p("Flat", "th"), _p("Member", "th")]
            + [_p(b["label"], "th_r") for b in buckets]
            + [_p("Total Due Rs.", "th_r"), _p("Due since", "th"), _p("Last payment", "th")])
    rows = [head]
    for i, r in enumerate(data["flats"], 1):
        last = (f"{date.fromisoformat(r['last_payment_date']):%d-%m-%Y} · Rs. {_inr(r['last_payment_amount'])}"
                if r["last_payment_date"] else "—")
        rows.append([_p(i, "td"), _p(r["flat_label"], "td"), _p(r["member_name"], "td")]
                    + [_p(_m(r["buckets"].get(b["key"])), "td_r") for b in buckets]
                    + [_p(_inr(r["total"]), "td_rb"),
                       _p(f"{date.fromisoformat(r['oldest_due_date']):%d-%m-%Y}", "td"), _p(last, "td")])
    totals = {b["key"]: sum(Decimal(r["buckets"].get(b["key"]) or 0) for r in data["flats"]) for b in buckets}
    grand = sum(Decimal(r["total"]) for r in data["flats"])
    rows.append([_p("", "td"), _p("TOTAL", "td"), _p(f"{len(data['flats'])} flats", "td")]
                + [_p(_m(totals[b["key"]]), "td_rb") for b in buckets]
                + [_p(_inr(grand), "td_rb"), "", ""])

    fixed = [12 * mm, 26 * mm, 52 * mm] + [24 * mm] * len(buckets) + [28 * mm, 22 * mm]
    widths = fixed + [width - sum(fixed)]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    if not data["flats"]:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("No member is in default.", P["note"]))

    notes = [f"Amounts are aged from each bill's due date. Payments made on account are set off against the "
             f"oldest bills first."]
    if s.get("interest_rate_pct"):
        notes.append(f"Simple interest at {s['interest_rate_pct']}% p.a. is charged on arrears as per the "
                     f"society's bye-laws and appears on the next bill.")
    for n in notes:
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph(escape(f"Note: {n}"), P["note"]))
    story.append(Spacer(1, 12 * mm))
    sign = Table([[_p(f"For {name.upper()}", "sign")], [Spacer(1, 10 * mm)], [_p("Hon. Secretary", "sign")]],
                 colWidths=[70 * mm], hAlign="RIGHT")
    sign.setStyle(TableStyle([("LINEABOVE", (0, 2), (0, 2), 0.8, INK)]))
    story.append(KeepTogether([sign]))

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · List of Defaulters")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
