"""The depreciation schedule as the office prints it: the society's letterhead, the year, one line per asset (cost,
opening book value, depreciation for the year, closing book value), the totals, the journal that would book it and
the assets left out until their setup is complete. Read-only: it formats what the API returns."""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, _inr, society_header

_b = S["cell"]
P = {
    "title": ParagraphStyle("dp_title", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("dp_sub", parent=S["centre_small"], fontSize=8.5),
    "h": ParagraphStyle("dp_h", parent=_b, fontName="Helvetica-Bold", fontSize=9, leading=11),
    "th": ParagraphStyle("dp_th", parent=_b, fontName="Helvetica-Bold", fontSize=7.6, leading=9),
    "th_r": ParagraphStyle("dp_th_r", parent=_b, fontName="Helvetica-Bold", fontSize=7.6, leading=9, alignment=2),
    "td": ParagraphStyle("dp_td", parent=_b, fontSize=7.8, leading=9.6),
    "td_r": ParagraphStyle("dp_td_r", parent=_b, fontSize=7.8, leading=9.6, alignment=2),
    "td_rb": ParagraphStyle("dp_td_rb", parent=_b, fontName="Helvetica-Bold", fontSize=7.8, leading=9.6, alignment=2),
    "td_b": ParagraphStyle("dp_td_b", parent=_b, fontName="Helvetica-Bold", fontSize=7.8, leading=9.6),
    "note": ParagraphStyle("dp_note", parent=_b, fontSize=7.6, leading=9.6, textColor=MUTED),
}
METHOD = {"wdv": "WDV", "slm": "SLM"}


def _p(text, style="td") -> Paragraph:
    return Paragraph(escape(str(text if text not in (None, "") else "—")), P[style])


def _d(v) -> str:
    return date.fromisoformat(v).strftime("%d-%m-%Y") if v else "—"


def _grid(rows, widths, total_last=False) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    style = [("BOX", (0, 0), (-1, -1), 0.8, INK), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
             ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if total_last:
        style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, INK))
    t.setStyle(TableStyle(style))
    return t


def render_depreciation_pdf(rep: dict, society, *, compress: bool = True) -> bytes:
    """`rep`: the schedule as the API returns it."""
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=8 * mm,
                            bottomMargin=12 * mm, title="Depreciation Schedule", author=name,
                            pageCompression=1 if compress else 0)
    width = doc.width
    story = [*society_header(society, width), Spacer(1, 4 * mm), Paragraph("DEPRECIATION SCHEDULE", P["title"]),
             Paragraph(escape(f"Financial year {rep['fy']} ({_d(rep['from'])} to {_d(rep['to'])}). Depreciation is for the "
                              "days each asset was in use; book value is cost less depreciation."), P["sub"]),
             Spacer(1, 3 * mm)]

    head = [_p(h, "th") for h in ("Sr.", "Asset", "Method", "Put to use")] + \
           [_p(h, "th_r") for h in ("Rate %", "Cost Rs.", "Book value at start Rs.", "Depreciation Rs.", "Book value at end Rs.")]
    rows = [head]
    for i, r in enumerate(rep["rows"], 1):
        rows.append([_p(i), _p(f"{r['asset_code']} · {r['name']}"), _p(METHOD.get(r["method"], r["method"])),
                     _p(_d(r["start"])), _p(r["rate"], "td_r"), _p(_inr(r["cost"]), "td_r"),
                     _p(_inr(r["opening_wdv"]), "td_r"), _p(_inr(r["depreciation"]), "td_rb"),
                     _p(_inr(r["closing_wdv"]), "td_r")])
    t = rep["totals"]
    rows.append(["", _p("TOTAL", "td_b"), "", "", "", _p(_inr(t["cost"]), "td_rb"), _p(_inr(t["opening_wdv"]), "td_rb"),
                 _p(_inr(t["depreciation"]), "td_rb"), _p(_inr(t["closing_wdv"]), "td_rb")])
    fixed = [10 * mm, 0, 16 * mm, 22 * mm, 15 * mm, 28 * mm, 34 * mm, 30 * mm, 34 * mm]
    fixed[1] = width - sum(fixed)
    story.append(_grid(rows, fixed, total_last=True))
    if not rep["rows"]:
        story += [Spacer(1, 3 * mm), Paragraph("No asset is being depreciated this year.", P["note"])]

    j = rep["journal"]
    if Decimal(j["debit"]["amount"]) > 0:
        jr = [[_p("Journal to book the year's depreciation (review before entering)", "th"), _p("Debit Rs.", "th_r"), _p("Credit Rs.", "th_r")],
              [_p(f"Dr {j['debit']['ledger']}"), _p(_inr(j["debit"]["amount"]), "td_r"), ""]]
        for c in j["credits"]:
            jr.append([_p(f"    Cr {c['ledger']}"), "", _p(_inr(c["amount"]), "td_r")])
        story += [Spacer(1, 5 * mm), KeepTogether([_grid(jr, [width - 70 * mm, 35 * mm, 35 * mm])]), Spacer(1, 1 * mm),
                  Paragraph("This is a calculation only: nothing has been posted to the books. The fixed-asset ledgers carry "
                            "book value, so depreciation is credited to them.", P["note"])]

    if rep["problems"]:
        pr = [[_p("Left out until their setup is complete", "th"), _p("What is missing", "th")]]
        for p in rep["problems"]:
            pr.append([_p(f"{p['asset_code']} · {p['name']}"), _p("; ".join(p["issues"]))])
        story += [Spacer(1, 5 * mm), KeepTogether([_grid(pr, [width * 0.4, width * 0.6])])]

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · Depreciation Schedule {rep['fy']}")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
