"""The vehicle report as a printout (PDF) and as a spreadsheet (Excel): the same four parts the screen shows, in full."""
from datetime import date, datetime
from io import BytesIO
from typing import List, Optional
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
    "title": ParagraphStyle("vr_title", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("vr_sub", parent=S["centre_small"], fontSize=8.5),
    "h": ParagraphStyle("vr_h", parent=_b, fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceBefore=4),
    "th": ParagraphStyle("vr_th", parent=_b, fontName="Helvetica-Bold", fontSize=7.8, leading=9.5),
    "td": ParagraphStyle("vr_td", parent=_b, fontSize=7.8, leading=9.6),
    "line": ParagraphStyle("vr_line", parent=_b, fontSize=8.5, leading=11),
    "note": ParagraphStyle("vr_note", parent=_b, fontSize=7.8, leading=10, textColor=MUTED),
}
INSURANCE_WORDS = {"expired": "Expired", "soon": "Expires soon", "ok": "Valid", "none": "Not recorded"}
WHO_WORDS = {"resident": "Resident", "visitor": "Visitor", "unknown": "Unknown"}


def _date(text: Optional[str]) -> str:
    try:
        return date.fromisoformat(text).strftime("%d-%m-%Y") if text else "-"
    except ValueError:
        return text or "-"


def _clock(iso: Optional[str], tz_name: str) -> str:
    """'05-11-2026 14:32' on the society's clock, for a UTC 'Z' time."""
    if not iso:
        return "-"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return d.astimezone(ZoneInfo(tz_name)).strftime("%d-%m-%Y %H:%M")


def _minutes(m: Optional[int]) -> str:
    if m is None:
        return "-"
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m} min"


def _filters(data: dict) -> str:
    bits = [data["month_label"] + " (violations and gate)", "as on " + _date(data["as_on"]) + " (vehicles and parking)"]
    if data.get("flat"):
        bits.append("Flat " + data["flat"])
    elif data.get("wing"):
        bits.append("Wing " + data["wing"])
    return " · ".join(bits)


# ── PDF ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def render_vehicle_report_pdf(data: dict, society, *, compress: bool = True) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=8 * mm, bottomMargin=12 * mm,
                            title="Vehicle Report", author=name, pageCompression=1 if compress else 0)
    tz = data.get("timezone") or "Asia/Kolkata"

    def para(text, style="td"):
        return Paragraph(escape(str(text if text not in (None, "") else "-")), P[style])

    def table(headers: List[str], rows: List[list], weights: List[float]):
        unit = doc.width / sum(weights)
        t = Table([[para(h, "th") for h in headers]] + [[para(c) for c in r] for r in rows],
                  colWidths=[w * unit for w in weights], repeatRows=1)
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, INK), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        return t

    def line(text):
        return Paragraph(escape(text), P["line"])

    def counted(d: dict) -> str:
        return ", ".join(f"{k} {v}" for k, v in d.items()) or "none"

    story = [*society_header(society, doc.width), Spacer(1, 4 * mm), Paragraph("VEHICLE REPORT", P["title"]),
             Paragraph(escape(_filters(data)), P["sub"]), Spacer(1, 3 * mm)]

    # 1. Vehicles
    v = data["vehicles"]
    s = v["summary"]
    story += [Paragraph("1. Registered vehicles", P["h"]),
              line(f"{s['total']} vehicles: {s['with_parking']} with parking, {s['without_parking']} without."),
              line(f"By type: {counted(s['by_type'])}."),
              line(f"Insurance: {s['insurance_expired']} expired, {s['insurance_soon']} expiring within 30 days, "
                   f"{s['insurance_missing']} not recorded."), Spacer(1, 2 * mm)]
    if v["rows"]:
        story.append(table(["Vehicle", "Type", "Make / model", "Flat", "Owner", "Parking", "Insurance"],
                           [[r["vehicle_number"], r["type"], " ".join(p for p in (r["make_model"], r["color"]) if p), r["flat"],
                             r["owner"], r["parking_slot"] or "None",
                             INSURANCE_WORDS[r["insurance"]] + (f" ({_date(r['insurance_expiry'])})" if r["insurance_expiry"] else "")]
                            for r in v["rows"]], [1.5, 1, 1.8, 1, 1.8, 1, 2]))
    else:
        story.append(Paragraph("No vehicle on record for this selection.", P["note"]))
    if v["flats_without_vehicle"]:
        story += [Spacer(1, 2 * mm), line(f"Occupied flats with no vehicle on record ({s['flats_without_vehicle']}): "
                                          + ", ".join(v["flats_without_vehicle"]) + ".")]

    # 2. Parking
    k = data["parking"]
    ps = k["summary"]
    story += [Spacer(1, 4 * mm), Paragraph("2. Parking", P["h"]),
              line(f"{ps['slots']} slots: {ps['allotted']} allotted, {ps['free']} free, {ps['blocked']} blocked or under repair.")]
    if k["zones"]:
        story += [Spacer(1, 2 * mm), table(["Zone", "Slots", "Allotted", "Free", "Reserved", "Blocked / repair"],
                                           [[f"{z['zone']} {('(' + z['code'] + ')') if z['code'] else ''}".strip(), z["total"],
                                             z["allotted"], z["free"], z["reserved"], z["blocked"]] for z in k["zones"]],
                                           [3, 1, 1, 1, 1, 1.4])]
    if k["flats_short"]:
        story += [Spacer(1, 3 * mm), line("Flats with more vehicles than parking:"),
                  table(["Flat", "Vehicles", "With parking", "Without"],
                        [[f["flat"], f["vehicles"], f["with_parking"], f["without_parking"]] for f in k["flats_short"]],
                        [2, 1, 1, 1])]
    if k["ending_soon"]:
        story += [Spacer(1, 3 * mm), line("Parking that ends within 30 days:"),
                  table(["Slot", "Flat", "Vehicle", "Ends"],
                        [[e["slot"], e["flat"], e["vehicle"], _date(e["ends"])] for e in k["ending_soon"]], [1, 1.4, 1.6, 1.2])]

    # 3. Violations
    w = data["violations"]
    vs = w["summary"]
    story += [Spacer(1, 4 * mm), Paragraph(f"3. Parking violations - {data['month_label']}", P["h"]),
              line(f"{vs['total']} violations: {vs['open']} open, {vs['resolved']} resolved. By type: {counted(vs['by_type'])}."),
              line(f"Fines: Rs {vs['fines_charged']:,} charged ({vs['fines_on_bills']:,} already on bills), "
                   f"Rs {vs['fines_taken_off']:,} taken off, Rs {vs['fines_not_charged']:,} set but not charged."),
              Spacer(1, 2 * mm)]
    if w["rows"]:
        story.append(table(["Date", "Vehicle", "Violation", "Flat", "Slot", "Fine", "Fine status", "Resolved"],
                           [[_date(r["date"]), r["vehicle_number"], r["type"], r["flat"], r["slot"],
                             f"Rs {r['fine']:,}" if r["fine"] else "-", r["fine_status"], "Yes" if r["resolved"] else "No"]
                            for r in w["rows"]], [1.1, 1.5, 1.9, 1.1, 0.8, 1, 1.5, 0.9]))
    else:
        story.append(Paragraph("No violation this month.", P["note"]))
    if w["repeat_offenders"]:
        story += [Spacer(1, 2 * mm), line("Repeat offenders: " + ", ".join(
            f"{o['vehicle_number']}{(' (' + o['flat'] + ')') if o['flat'] else ''} x{o['count']}" for o in w["repeat_offenders"]) + ".")]

    # 4. Gate
    g = data["gate"]
    gs = g["summary"]
    stay = _minutes(gs["visitor_avg_stay_minutes"])
    story += [Spacer(1, 4 * mm), Paragraph(f"4. Gate and visitor vehicles - {data['month_label']}", P["h"]),
              line(f"{gs['total']} movements: {gs['entries']} in, {gs['exits']} out. Residents {gs['residents']}, "
                   f"visitors {gs['visitors']}, unknown {gs['unknown']}; {gs['not_allowed']} not allowed in."),
              line(f"Visitor parking: {gs['visitor_visits']} visits, average stay {stay}, {gs['visitor_overstayed']} stayed past the "
                   f"time given; {gs['visitor_inside']} inside now."), Spacer(1, 2 * mm)]
    if g["visitors_inside"]:
        story += [line("Visitor vehicles inside now:"),
                  table(["Vehicle", "Visiting", "Since", "Time given", "Inside for", "Slot"],
                        [[r["vehicle_number"], r["host_flat"], _clock(r["since"], tz), f"{r['expected_hours']} h",
                          _minutes(r["minutes"]) + (" (overstayed)" if r["overstayed"] else ""), r["slot"]]
                         for r in g["visitors_inside"]], [1.5, 1.2, 1.8, 1, 2, 0.8]), Spacer(1, 3 * mm)]
    if g["rows"]:
        story.append(table(["Time", "Vehicle", "In / out", "Who", "Flat", "How", "Allowed"],
                           [[_clock(r["time"], tz), r["vehicle_number"], r["direction"], WHO_WORDS[r["who"]], r["flat"], r["method"],
                             "Yes" if r["allowed"] else "No"] for r in g["rows"]], [1.8, 1.6, 0.9, 1.1, 1.1, 1, 0.9]))
    else:
        story.append(Paragraph("No vehicle movement recorded this month.", P["note"]))

    printed = datetime.now(ZoneInfo(tz)).strftime("%d %b %Y %H:%M")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · Vehicle Report")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ── Excel ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def render_vehicle_report_xlsx(data: dict, society) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    tz = data.get("timezone") or "Asia/Kolkata"
    name = society.name if society else "Society"
    wb = Workbook()
    fill = PatternFill("solid", fgColor="EDEDED")

    def put(ws, row: int, col: int, value, *, bold=False):
        cell = ws.cell(row=row, column=col)
        cell.value = value
        if isinstance(value, str):
            cell.data_type = "s"          # always text: a plate or note starting with = + - @ must not become a formula
        if bold:
            cell.font = Font(bold=True)
        return cell

    def sheet(title: str, headers: List[str], rows: List[list], widths: List[int], first=False, heading: Optional[str] = None):
        ws = wb.active if first else wb.create_sheet()
        ws.title = title
        put(ws, 1, 1, name, bold=True)
        put(ws, 2, 1, heading or title, bold=True)
        put(ws, 3, 1, _filters(data))
        for j, h in enumerate(headers, 1):
            c = put(ws, 5, j, h, bold=True)
            c.fill = fill
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for i, r in enumerate(rows, 6):
            for j, value in enumerate(r, 1):
                put(ws, i, j, value if isinstance(value, (int, float)) and not isinstance(value, bool) else ("" if value is None else str(value)))
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
        ws.freeze_panes = ws.cell(row=6, column=1)
        return ws

    s, ps, vs, gs = data["vehicles"]["summary"], data["parking"]["summary"], data["violations"]["summary"], data["gate"]["summary"]
    sheet("Summary", ["Measure", "Value"], [
        ["Vehicles registered", s["total"]], ["With parking", s["with_parking"]], ["Without parking", s["without_parking"]],
        ["Insurance expired", s["insurance_expired"]], ["Insurance expiring within 30 days", s["insurance_soon"]],
        ["Insurance not recorded", s["insurance_missing"]], ["Occupied flats with no vehicle", s["flats_without_vehicle"]],
        ["Parking slots", ps["slots"]], ["Slots allotted", ps["allotted"]], ["Slots free", ps["free"]],
        ["Flats with more vehicles than parking", ps["flats_short"]],
        [f"Violations ({data['month_label']})", vs["total"]], ["Violations open", vs["open"]],
        ["Fines charged (Rs)", vs["fines_charged"]], ["Fines taken off (Rs)", vs["fines_taken_off"]],
        [f"Gate movements ({data['month_label']})", gs["total"]], ["Entries", gs["entries"]], ["Exits", gs["exits"]],
        ["Not allowed in", gs["not_allowed"]], ["Visitor vehicles inside now", gs["visitor_inside"]],
        ["Visitor stays past the time given", gs["visitor_overstayed"]],
    ], [44, 14], first=True, heading="Vehicle report - summary")
    sheet("Vehicles", ["Vehicle", "Type", "Make / model", "Colour", "Flat", "Owner", "Owner or tenant", "Parking slot", "Insurance",
                       "Insurance expiry"],
          [[r["vehicle_number"], r["type"], r["make_model"], r["color"], r["flat"], r["owner"], r["category"],
            r["parking_slot"] or "None", INSURANCE_WORDS[r["insurance"]], _date(r["insurance_expiry"]) if r["insurance_expiry"] else ""]
           for r in data["vehicles"]["rows"]], [16, 12, 22, 12, 10, 24, 18, 12, 14, 14], heading="Registered vehicles")
    sheet("Parking", ["Zone", "Code", "Slots", "Allotted", "Free", "Reserved", "Blocked / repair"],
          [[z["zone"], z["code"], z["total"], z["allotted"], z["free"], z["reserved"], z["blocked"]] for z in data["parking"]["zones"]],
          [24, 8, 8, 10, 8, 10, 16], heading="Parking by zone")
    sheet("Flats short of parking", ["Flat", "Vehicles", "With parking", "Without parking"],
          [[f["flat"], f["vehicles"], f["with_parking"], f["without_parking"]] for f in data["parking"]["flats_short"]],
          [14, 10, 14, 16], heading="Flats with more vehicles than parking")
    sheet("Violations", ["Date", "Vehicle", "Violation", "Flat", "Slot", "Description", "Fine (Rs)", "Fine status", "Resolved"],
          [[_date(r["date"]), r["vehicle_number"], r["type"], r["flat"], r["slot"], r["description"], r["fine"] or "",
            r["fine_status"], "Yes" if r["resolved"] else "No"] for r in data["violations"]["rows"]],
          [12, 16, 22, 10, 8, 36, 10, 16, 10], heading=f"Parking violations - {data['month_label']}")
    sheet("Gate log", ["Time", "Vehicle", "In / out", "Who", "Flat", "How", "Allowed", "Notes"],
          [[_clock(r["time"], tz), r["vehicle_number"], r["direction"], WHO_WORDS[r["who"]], r["flat"], r["method"],
            "Yes" if r["allowed"] else "No", r["notes"]] for r in data["gate"]["rows"]],
          [18, 16, 9, 10, 10, 11, 9, 30], heading=f"Gate log - {data['month_label']}")
    sheet("Visitors inside", ["Vehicle", "Visiting", "Since", "Time given (hours)", "Inside for", "Overstayed", "Slot"],
          [[r["vehicle_number"], r["host_flat"], _clock(r["since"], tz), r["expected_hours"], _minutes(r["minutes"]),
            "Yes" if r["overstayed"] else "No", r["slot"]] for r in data["gate"]["visitors_inside"]],
          [16, 12, 18, 18, 14, 12, 8], heading="Visitor vehicles inside now")
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
