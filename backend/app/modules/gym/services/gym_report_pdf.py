"""The gym attendance report, printed: the society's letterhead, the week or month, the totals, day by day, and each
member's visits."""
from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, society_header

_b = S["cell"]
P = {
    "title": ParagraphStyle("gy_title", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("gy_sub", parent=S["centre_small"], fontSize=9),
    "h": ParagraphStyle("gy_h", parent=_b, fontName="Helvetica-Bold", fontSize=9.5, leading=12),
    "th": ParagraphStyle("gy_th", parent=_b, fontName="Helvetica-Bold", fontSize=8.5, leading=10),
    "th_r": ParagraphStyle("gy_th_r", parent=_b, fontName="Helvetica-Bold", fontSize=8.5, leading=10, alignment=2),
    "td": ParagraphStyle("gy_td", parent=_b, fontSize=8.5, leading=10.5),
    "td_r": ParagraphStyle("gy_td_r", parent=_b, fontSize=8.5, leading=10.5, alignment=2),
    "note": ParagraphStyle("gy_note", parent=_b, fontSize=8, leading=10, textColor=MUTED),
}


def _p(text, style: str) -> Paragraph:
    return Paragraph(escape(str(text if text not in (None, "") else "-")), P[style])


def _hours(minutes) -> str:
    if not minutes:
        return "-"
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes} min"


def _grid(rows, widths):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def render_gym_report_pdf(data: dict, society, *, compress: bool = True) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=10 * mm,
                            bottomMargin=14 * mm, title="Gym Attendance Report", author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    t = data["totals"]
    story = [*society_header(society, width), Spacer(1, 4 * mm),
             Paragraph("GYM ATTENDANCE REPORT", P["title"]), Paragraph(escape(data["label"]), P["sub"]), Spacer(1, 4 * mm)]

    busiest = date.fromisoformat(t["busiest_day"]).strftime("%a %d %b") if t["busiest_day"] else "-"
    summary = [
        [_p("Visits", "th"), _p("Different members", "th"), _p("Different flats", "th"), _p("Average stay", "th"),
         _p("Busiest day", "th"), _p("Not ticked out", "th")],
        [_p(t["visits"], "td"), _p(t["unique_members"], "td"), _p(t["unique_flats"], "td"),
         _p(_hours(t["average_minutes"]), "td"), _p(busiest, "td"), _p(t["not_checked_out"], "td")],
    ]
    story += [_grid(summary, [width / 6] * 6), Spacer(1, 5 * mm), Paragraph("Day by day", P["h"]), Spacer(1, 1.5 * mm)]

    day_rows = [[_p("Date", "th"), _p("Visits", "th_r"), _p("Different members", "th_r")]]
    for d in data["days"]:
        day_rows.append([_p(date.fromisoformat(d["date"]).strftime("%a %d %b %Y"), "td"),
                         _p(d["visits"], "td_r"), _p(d["unique_members"], "td_r")])
    story += [_grid(day_rows, [width * 0.5, width * 0.25, width * 0.25]), Spacer(1, 5 * mm),
              Paragraph("Members", P["h"]), Spacer(1, 1.5 * mm)]

    if data["members"]:
        rows = [[_p("Sr.", "th"), _p("Member", "th"), _p("Flat", "th"), _p("Visits", "th_r"), _p("Time in the gym", "th_r")]]
        for i, m in enumerate(data["members"], 1):
            rows.append([_p(i, "td"), _p(m["name"], "td"), _p(m["flat_label"], "td"), _p(m["visits"], "td_r"),
                         _p(_hours(m["total_minutes"]), "td_r")])
        story.append(_grid(rows, [width * 0.08, width * 0.42, width * 0.18, width * 0.12, width * 0.20]))
    else:
        story.append(Paragraph("Nobody used the gym in this period.", P["note"]))
    story += [Spacer(1, 3 * mm), Paragraph(
        "Time in the gym counts only visits that were ticked out the same day. A visit nobody ticked out is counted as a "
        "visit but has no length.", P["note"])]

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 7 * mm, f"{name} · Gym Attendance Report")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 7 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
