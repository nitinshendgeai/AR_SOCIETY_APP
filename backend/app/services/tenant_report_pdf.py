"""
The Tenants report as the office prints it: the society's letterhead, "Tenants Report", the filters the list was
showing, one line per tenant (flat, phone, rent, agreement end, police verification, KYC) and a count.
Read-only: it formats rows the tenants list already returns.
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import List, Optional
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, _inr, society_header

_b = S["cell"]
P = {
    "title": ParagraphStyle("tr_title", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("tr_sub", parent=S["centre_small"], fontSize=8.5),
    "th": ParagraphStyle("tr_th", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5),
    "th_r": ParagraphStyle("tr_th_r", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5, alignment=2),
    "td": ParagraphStyle("tr_td", parent=_b, fontSize=8, leading=9.8),
    "td_r": ParagraphStyle("tr_td_r", parent=_b, fontSize=8, leading=9.8, alignment=2),
    "td_rb": ParagraphStyle("tr_td_rb", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.8, alignment=2),
    "note": ParagraphStyle("tr_note", parent=_b, fontSize=7.8, leading=10, textColor=MUTED),
}

_POLICE = {"pending": "Pending", "submitted": "Submitted", "verified": "Verified", "rejected": "Rejected"}


def _p(text, style: str) -> Paragraph:
    return Paragraph(escape(str(text if text not in (None, "") else "—")), P[style])


def _day(d: Optional[date]) -> str:
    return d.strftime("%d-%m-%Y") if d else "—"


def render_tenants_pdf(rows: List[dict], filters: List[str], society, *, compress: bool = True) -> bytes:
    """`rows`: one dict per tenant — name, flat, phone, email, rent (Decimal or None), agreement_end (date or None),
    police (status string or None), kyc (bool), moved_in (date or None). `filters`: the filters in force, in words."""
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=8 * mm, bottomMargin=12 * mm, title="Tenants Report", author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    sub = "Filters: " + ("; ".join(filters) if filters else "none (every tenant on record)")
    story = [*society_header(society, width), Spacer(1, 4 * mm), Paragraph("TENANTS REPORT", P["title"]),
             Paragraph(escape(sub), P["sub"]), Spacer(1, 3 * mm)]

    head = [_p(h, "th") for h in ("Sr.", "Tenant", "Flat", "Phone", "Email")] + [_p("Rent / month Rs.", "th_r")] + \
           [_p(h, "th") for h in ("Moved in", "Agreement ends", "Police", "KYC")]
    table = [head]
    for i, r in enumerate(rows, 1):
        table.append([
            _p(i, "td"), _p(r["name"], "td"), _p(r["flat"], "td"), _p(r.get("phone"), "td"), _p(r.get("email"), "td"),
            _p(_inr(r["rent"]) if r.get("rent") is not None and Decimal(r["rent"]) != 0 else None, "td_r"),
            _p(_day(r.get("moved_in")), "td"), _p(_day(r.get("agreement_end")), "td"),
            _p(_POLICE.get(r.get("police") or "", r.get("police")), "td"),
            _p("Verified" if r.get("kyc") else "Not verified", "td"),
        ])
    rent_total = sum((Decimal(r["rent"]) for r in rows if r.get("rent") is not None), Decimal(0))
    table.append(["", _p("TOTAL", "td"), _p(f"{len(rows)} tenant{'' if len(rows) == 1 else 's'}", "td"), "", "",
                  _p(_inr(rent_total), "td_rb"), "", "", "", ""])

    fixed = [10 * mm, 48 * mm, 22 * mm, 28 * mm, 52 * mm, 28 * mm, 22 * mm, 26 * mm, 22 * mm]
    t = Table(table, colWidths=fixed + [width - sum(fixed)], repeatRows=1)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    if not rows:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("No tenant matches these filters.", P["note"]))

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · Tenants Report")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
