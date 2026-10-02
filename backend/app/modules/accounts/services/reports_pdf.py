"""
The financial statements printed the way a housing society presents them to
its auditor and the AGM: the society's letterhead, the statement's heading,
and —

- two-sided statements (Income & Expenditure, Balance Sheet, Receipts &
  Payments) side by side on landscape A4, each side with the previous
  year's figures, the particulars and this year's figures, groups in bold
  with their ledgers under them, and both sides totalled on one line;
- tables (Trial Balance, Schedule of Funds) on portrait A4;

then signature lines for the Hon. Chairman, Secretary and Treasurer "For
<Society>", and "As per our report of even date" for the statutory auditor.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from io import BytesIO
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, _inr, society_header

_base = S["cell"]
P = {
    "heading": ParagraphStyle("rp_heading", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("rp_sub", parent=S["centre_small"], fontSize=8.5),
    "th": ParagraphStyle("rp_th", parent=_base, fontName="Helvetica-Bold", fontSize=8.5, leading=10),
    "th_r": ParagraphStyle("rp_th_r", parent=_base, fontName="Helvetica-Bold", fontSize=8.5, leading=10,
                           alignment=2),
    "group": ParagraphStyle("rp_group", parent=_base, fontName="Helvetica-Bold", fontSize=8.5, leading=10.5),
    "item": ParagraphStyle("rp_item", parent=_base, fontSize=8, leading=10, leftIndent=8, textColor=INK),
    "amt": ParagraphStyle("rp_amt", parent=_base, fontSize=8, leading=10, alignment=2),
    "amt_b": ParagraphStyle("rp_amt_b", parent=_base, fontName="Helvetica-Bold", fontSize=8.5, leading=10.5,
                            alignment=2),
    "note": ParagraphStyle("rp_note", parent=_base, fontSize=7.8, leading=10, textColor=MUTED),
    "sign": ParagraphStyle("rp_sign", parent=S["sign"], fontSize=7.8),
}


def _money(v: str) -> str:
    """'(1,234.00)' for a negative amount, '' for a blank."""
    if not v:
        return ""
    d = Decimal(v)
    return f"({_inr(-d)})" if d < 0 else _inr(d)


def _p(text: str, style: str) -> Paragraph:
    return Paragraph(escape(text or ""), P[style])


def _side_rows(side: dict, ncols: int) -> List[list]:
    """A side's lines as [amount cells…, particulars] in display order:
    previous years first, current year last."""
    rows = []
    for sec in side["sections"]:
        if sec.get("title"):
            total = sec.get("total") or [""] * ncols
            rows.append(("group", sec["title"], total))
        for r in sec["rows"]:
            rows.append(("bold" if r.get("bold") else "item", r["label"], r.get("amounts") or [""] * ncols))
    return rows


def _two_sided(report: dict, width: float) -> Table:
    cols = report["columns"]          # [current, previous?]
    n = len(cols)
    amount_w = 24 * mm
    part_w = width / 2 - amount_w * n
    widths = ([amount_w] * (n - 1) + [part_w] + [amount_w]) * 2

    def header(side: dict) -> list:
        prev = [_p(f"FY {c} Rs.", "th_r") for c in cols[1:]][::-1]
        return prev + [_p(side["title"].upper(), "th"), _p(f"FY {cols[0]} Rs.", "th_r")]

    def cells(kind: str, label: str, amounts: list) -> list:
        amt_style = "amt" if kind == "item" else "amt_b"
        label_style = "item" if kind == "item" else "group"
        prev = [_p(_money(a), amt_style) for a in amounts[1:]][::-1]
        return prev + [_p(label, label_style), _p(_money(amounts[0]), amt_style)]

    left, right = report["sides"]
    lrows, rrows = _side_rows(left, n), _side_rows(right, n)
    blank = [""] * (n + 1)
    data = [header(left) + header(right)]
    for i in range(max(len(lrows), len(rrows))):
        data.append((cells(*lrows[i]) if i < len(lrows) else blank)
                    + (cells(*rrows[i]) if i < len(rrows) else blank))
    data.append(cells("bold", "TOTAL", left["total"]) + cells("bold", "TOTAL", right["total"]))

    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("LINEAFTER", (n, 0), (n, -1), 0.8, INK),               # between the two sides
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for c in range(len(widths)):                                 # light rules between columns
        if c not in (n, len(widths) - 1):
            style.append(("LINEAFTER", (c, 0), (c, -1), 0.3, RULE))
    t.setStyle(TableStyle(style))
    return t


def _table(report: dict, width: float) -> Table:
    cols = report["columns"]
    amount_w = 30 * mm
    widths = [width - amount_w * len(cols)] + [amount_w] * len(cols)
    # The PDF's built-in fonts have no rupee sign.
    data = [[_p("PARTICULARS", "th")] + [_p(c.replace("(₹)", "Rs.").upper(), "th_r") for c in cols]]
    group_rows = []
    for r in report["rows"]:
        bold = r.get("bold") or r.get("level", 1) == 0
        if bold:
            group_rows.append(len(data))
        label = f"{r['code']}  {r['label']}" if r.get("code") else r["label"]
        data.append([_p(label, "group" if bold else "item")]
                    + [_p(_money(c), "amt_b" if bold else "amt") for c in r["cells"]])
    data.append([_p("TOTAL", "group")] + [_p(_money(c), "amt_b") for c in report["totals"]])
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
    ]
    for c in range(len(widths) - 1):
        style.append(("LINEAFTER", (c, 0), (c, -1), 0.3, RULE))
    for r in group_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F6F6F6")))
    t.setStyle(TableStyle(style))
    return t


def _signatures(society_name: str, width: float) -> Table:
    """Four signature lines with gaps between them: the auditor's, then the
    Chairman's, Secretary's and Treasurer's "For <Society>"."""
    gap = 10 * mm
    w = (width - 3 * gap) / 4
    titles = ["Statutory Auditor", "Hon. Chairman", "Hon. Secretary", "Hon. Treasurer"]
    t = Table([
        [_p("As per our report of even date", "sign"), "", _p(f"For {society_name.upper()}", "sign"),
         "", "", "", ""],
        [Spacer(1, 12 * mm)] + [""] * 6,
        [x for title in titles for x in (_p(title, "sign"), "")][:-1],
    ], colWidths=[w, gap, w, gap, w, gap, w])
    t.setStyle(TableStyle([("SPAN", (2, 0), (6, 0))] + [
        ("LINEABOVE", (c, 2), (c, 2), 0.8, INK) for c in (0, 2, 4, 6)]))
    return t


def render_report_pdf(report: dict, society, *, compress: bool = True) -> bytes:
    two_sided = report["kind"] == "two_sided"
    pagesize = landscape(A4) if two_sided else A4
    buf = BytesIO()
    name = society.name if society else report.get("society_name") or "Society"
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=8 * mm, bottomMargin=12 * mm, title=report["heading"], author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    story = [*society_header(society, width), Spacer(1, 4 * mm),
             Paragraph(escape(report["heading"].upper()), P["heading"])]
    if report.get("provisional"):
        story.append(Paragraph("Provisional — the financial year is not over yet.", P["sub"]))
    story.append(Spacer(1, 3 * mm))
    story.append(_two_sided(report, width) if two_sided else _table(report, width))
    for note in report.get("notes") or []:
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph(escape(f"Note: {note}"), P["note"]))
    story.append(Spacer(1, 8 * mm))
    story.append(KeepTogether([_signatures(name, width)]))

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · {report['title']} · FY {report['fy']}")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
