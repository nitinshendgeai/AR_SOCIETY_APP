"""Printable duty sheets for staff who work from paper.

One A4 page per staff member per day: the society's letterhead, who and when, a
strip for the in and out times and signature, then each duty with its checklist as
a table of tick boxes and a remarks column, and signature lines for the staff
member and the supervisor. A supervisor later enters the filled sheet in the app
(Duties -> Enter from sheet), or staff tick the same items on their phone.

`render_blank_template_sheet` prints a template's checklist with the date and name
left blank, for a department that fills it in by hand every day.

`render_floor_sheets` / `render_blank_floor_sheet` print the floor-wise layout for housekeeping:
one page per wing with every floor as a row and the duty's checklist items as tick columns, so
one staff member covers all the floors of a wing on a single page.

The standard PDF fonts have no Devanagari glyphs, so checklist text prints in
English / Latin letters.
"""
from datetime import date, datetime
from io import BytesIO
from typing import List, Optional
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import BAND, INK, MUTED, RULE, S, society_header

BOX_H = 8.2 * mm
P = {
    "title": ParagraphStyle("ds_title", parent=S["title"], fontSize=13.5, leading=17),
    "hint": ParagraphStyle("ds_hint", parent=S["centre_small"], fontSize=8.2, leading=10.5),
    "body": ParagraphStyle("ds_body", parent=S["cell"], fontSize=9.2, leading=11.4),
    "bold": ParagraphStyle("ds_bold", parent=S["cell_b"], fontSize=9.2, leading=11.4),
    "label": ParagraphStyle("ds_label", parent=S["cell"], fontSize=8, leading=10, textColor=MUTED),
    "duty": ParagraphStyle("ds_duty", parent=S["cell_b"], fontSize=10, leading=12.5),
    "dim": ParagraphStyle("ds_dim", parent=S["cell"], fontSize=8, leading=10, textColor=MUTED),
    "head": ParagraphStyle("ds_head", parent=S["cell_cb"], fontSize=8.4, leading=10),
    "centre": ParagraphStyle("ds_centre", parent=S["cell_c"], fontSize=8, leading=10, textColor=MUTED),
    "done": ParagraphStyle("ds_done", parent=S["cell_cb"], fontSize=7.5, leading=9),
    "small": ParagraphStyle("ds_small", parent=S["cell"], fontSize=7.8, leading=9.6, textColor=MUTED),
}


def _p(text, style="body"):
    return Paragraph(escape(str(text or "")), P[style])


def _clock(t) -> str:
    return f"{t:%H:%M}" if t else ""


def _info_table(rows, width) -> Table:
    t = Table(rows, colWidths=[width * 0.14, width * 0.36, width * 0.14, width * 0.36])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("BACKGROUND", (0, 0), (0, -1), BAND), ("BACKGROUND", (2, 0), (2, -1), BAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _attendance_strip(width) -> Table:
    t = Table([[_p("IN time", "bold"), "", _p("OUT time", "bold"), "", _p("Staff signature", "bold"), ""]],
              colWidths=[width * 0.10, width * 0.16, width * 0.12, width * 0.16, width * 0.17, width * 0.29],
              rowHeights=[BOX_H + 2 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("BACKGROUND", (0, 0), (0, 0), BAND), ("BACKGROUND", (2, 0), (2, 0), BAND), ("BACKGROUND", (4, 0), (4, 0), BAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _items_table(heading_cells, item_rows, width) -> Table:
    """Header band for the duty, column titles, then one row per check item."""
    cols = [width * 0.06, width * 0.52, width * 0.10, width * 0.32]
    rows = [heading_cells, [_p("#", "head"), _p("Check", "head"), _p("Done", "head"), _p("Remarks", "head")]] + item_rows
    t = Table(rows, colWidths=cols, repeatRows=2)
    style = [
        ("GRID", (0, 1), (-1, -1), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("BACKGROUND", (0, 0), (-1, 0), BAND), ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EFEFEF")),
        ("SPAN", (0, 0), (-1, 0)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, 1), 2.5),
        # Item rows are padded tall enough to tick and write in; a row with a description grows.
        ("TOPPADDING", (0, 2), (-1, -1), 5.6), ("BOTTOMPADDING", (0, 2), (-1, -1), 5.6),
    ]
    t.setStyle(TableStyle(style))
    return t


def _sign_off(width) -> Table:
    """Room for the supervisor's remarks, then room to sign above each caption."""
    gap = width * 0.03
    cols = [width * 0.35, gap, width * 0.35, gap, width * 0.24]
    t = Table([
        [_p("Supervisor's remarks", "label"), "", "", "", ""],
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        [_p("Staff signature", "dim"), "", _p("Supervisor signature", "dim"), "", _p("Date", "dim")],
    ], colWidths=cols, rowHeights=[5 * mm, 12 * mm, 14 * mm, 5 * mm])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("SPAN", (0, 1), (-1, 1)),
        ("BOX", (0, 0), (-1, 1), 0.5, RULE),
        ("LINEABOVE", (0, 3), (0, 3), 0.8, INK), ("LINEABOVE", (2, 3), (2, 3), 0.8, INK),
        ("LINEABOVE", (4, 3), (4, 3), 0.8, INK),
        ("LEFTPADDING", (0, 3), (-1, 3), 1), ("TOPPADDING", (0, 3), (-1, 3), 1),
    ]))
    return t


def _duty_block(duty, index: int, width):
    window = " – ".join(x for x in (_clock(duty.start_time), _clock(duty.end_time)) if x)
    where = " · ".join(x for x in (duty.location, window) if x)
    heading = [Paragraph(
        f"<b>{index}. {escape(duty.duty_name)}</b>"
        + (f"  <font size=8 color='#555555'>{escape(where)}</font>" if where else ""), P["duty"]), "", "", ""]

    rows = []
    items = sorted(duty.checklist_items, key=lambda i: i.sequence)
    if items:
        for n, it in enumerate(items, 1):
            title = escape(it.title) + (" <b>*</b>" if it.is_required else "")
            if it.description:
                title += f"<br/><font size=7.5 color='#555555'>{escape(it.description)}</font>"
            rows.append([_p(n, "centre"), Paragraph(title, P["body"]),
                         _p("Done" if it.is_completed else "", "done"), _p(it.notes or "", "dim")])
    else:
        rows.append([_p(1, "centre"), _p("Duty completed", "body"),
                     _p("Done" if duty.is_completed else "", "done"), ""])
    block = [_items_table(heading, rows, width)]
    if duty.description:
        block.append(Spacer(1, 1 * mm))
        block.append(_p(duty.description, "dim"))
    block.append(Spacer(1, 3.5 * mm))
    return block


def _document(buf, society, title, compress):
    name = society.name if society else "Society"
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=8 * mm,
                             bottomMargin=10 * mm, title=title, author=name, pageCompression=1 if compress else 0)


def render_duty_sheets(society, tz: ZoneInfo, pages: List[dict], *, compress: bool = True) -> bytes:
    """`pages` is [{"staff": Staff, "date": date, "duties": [DutyAssignment]}], one per sheet."""
    buf = BytesIO()
    doc = _document(buf, society, "Daily duty sheet", compress)
    width = doc.width
    printed = datetime.now(tz).strftime("%d %b %Y %H:%M")
    story: list = []
    for number, page in enumerate(pages):
        staff, day, duties = page["staff"], page["date"], page["duties"]
        if number:
            story.append(PageBreak())
        story += society_header(society, width)
        story += [Spacer(1, 3 * mm), Paragraph("DAILY DUTY SHEET", P["title"]),
                  Paragraph("Tick each item when it is done and write a remark if anything is wrong. "
                            "Sign at the bottom. * means the item must be done.", P["hint"]),
                  Spacer(1, 2.5 * mm)]

        shift = staff.shift
        shift_text = (f"{shift.name} {_clock(shift.start_time)}–{_clock(shift.end_time)}" if shift else "—")
        role = " · ".join(x for x in (staff.department.value.title(), staff.designation_name) if x)
        story.append(_info_table([
            [_p("Name", "label"), _p(f"{staff.full_name} ({staff.employee_code})", "bold"),
             _p("Date", "label"), _p(f"{day:%a, %d %b %Y}", "bold")],
            [_p("Department", "label"), _p(role, "body"), _p("Shift", "label"), _p(shift_text, "body")],
        ], width))
        story += [Spacer(1, 2 * mm), _attendance_strip(width), Spacer(1, 4 * mm)]

        for index, duty in enumerate(duties, 1):
            story += _duty_block(duty, index, width)
        story += [Spacer(1, 1 * mm), KeepTogether([_sign_off(width), Spacer(1, 1.5 * mm),
                                                   _p(f"Printed {printed} IST · Sheet {staff.employee_code}-{day:%Y%m%d}", "small")])]
    doc.build(story)
    return buf.getvalue()


def render_blank_template_sheet(society, tz: ZoneInfo, template, *, compress: bool = True) -> bytes:
    """A template's checklist with the name, date and in/out left blank."""
    buf = BytesIO()
    doc = _document(buf, society, template.name, compress)
    width = doc.width
    printed = datetime.now(tz).strftime("%d %b %Y %H:%M")
    story = society_header(society, width)
    story += [Spacer(1, 3 * mm), Paragraph(escape(template.name.upper()), P["title"]),
              Paragraph("Tick each item when it is done and write a remark if anything is wrong. "
                        "Sign at the bottom. * means the item must be done.", P["hint"]),
              Spacer(1, 2.5 * mm)]
    story.append(_info_table([
        [_p("Name", "label"), "", _p("Date", "label"), ""],
        [_p("Department", "label"), _p(template.department.value.title(), "body"),
         _p("Shift", "label"), ""],
    ], width))
    story += [Spacer(1, 2 * mm), _attendance_strip(width), Spacer(1, 4 * mm)]

    rows = []
    for n, it in enumerate(sorted(template.items, key=lambda i: i.sequence), 1):
        title = escape(it.title) + (" <b>*</b>" if it.is_required else "")
        if it.description:
            title += f"<br/><font size=7.5 color='#555555'>{escape(it.description)}</font>"
        rows.append([_p(n, "centre"), Paragraph(title, P["body"]), "", ""])
    if not rows:
        rows.append([_p(1, "centre"), _p("Duty completed", "body"), "", ""])
    story.append(_items_table([Paragraph(f"<b>{escape(template.name)}</b>", P["duty"]), "", "", ""], rows, width))
    if template.description:
        story += [Spacer(1, 1 * mm), _p(template.description, "dim")]
    story += [Spacer(1, 4 * mm), KeepTogether([_sign_off(width), Spacer(1, 1.5 * mm),
                                               _p(f"Printed {printed} IST", "small")])]
    doc.build(story)
    return buf.getvalue()


# ── Floor-wise sheets (housekeeping) ──────────────────────────────────────────

FLOOR_COL, TIME_COL, INIT_COL = 28 * mm, 15 * mm, 17 * mm
MAX_ROW_H, MIN_ROW_H = 8.2 * mm, 5 * mm
# Space the letterhead, title, name block, in/out strip, column titles and sign-off use on a page.
CHROME_H = 152 * mm


def _floor_grid(columns, floors, width) -> Table:
    """Floors down the side, one tick column per checklist item, then time and initials."""
    n_items = len(columns)
    item_w = max((width - FLOOR_COL - TIME_COL - INIT_COL) / n_items, 9 * mm)
    head_style = ParagraphStyle("fg_head", parent=P["head"], fontSize=7.4 if n_items <= 8 else 6.4,
                                leading=8.6 if n_items <= 8 else 7.4)
    head = [Paragraph("<b>Floor</b>", P["head"])] + [
        Paragraph(escape(title) + ("&nbsp;*" if required else ""), head_style) for title, required in columns
    ] + [Paragraph("<b>Time</b>", P["head"]), Paragraph("<b>Initials</b>", P["head"])]
    row_h = max(MIN_ROW_H, min(MAX_ROW_H, (A4[1] - CHROME_H) / max(len(floors), 1)))
    rows = [head] + [[_p(label, "bold")] + [""] * n_items + ["", ""] for label in floors]
    t = Table(rows, colWidths=[FLOOR_COL] + [item_w] * n_items + [TIME_COL, INIT_COL],
              rowHeights=[None] + [row_h] * len(floors), repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, RULE), ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("BACKGROUND", (0, 0), (-1, 0), BAND), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F6F6F6")),
        ("TOPPADDING", (0, 0), (-1, 0), 3), ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("TOPPADDING", (0, 1), (-1, -1), 0), ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))
    return t


def _floor_page(society, width, printed, *, title, who_rows, columns, wing, footer):
    story = society_header(society, width)
    story += [Spacer(1, 3 * mm), Paragraph(escape(title.upper()), P["title"]),
              Paragraph("Tick each column when it is done on that floor, then write the time and your initials. "
                        "* means the item must be done on every floor.", P["hint"]),
              Spacer(1, 2.5 * mm), _info_table(who_rows, width), Spacer(1, 2 * mm), _attendance_strip(width),
              Spacer(1, 3 * mm), _floor_grid(columns, wing["floors"], width), Spacer(1, 3 * mm),
              KeepTogether([_sign_off(width), Spacer(1, 1.5 * mm), _p(f"Printed {printed} IST · {footer}", "small")])]
    return story


def _columns(items):
    """(title, required) for each checklist item in order; one 'Done' column when there are none."""
    return [(i.title, i.is_required) for i in sorted(items, key=lambda i: i.sequence)] or [("Done", False)]


def render_floor_sheets(society, tz: ZoneInfo, pages: List[dict], wings: List[dict], *, compress: bool = True) -> bytes:
    """One page per duty per wing. `wings` is [{"label": "Wing A", "floors": ["Ground", "Floor 1", ...]}]."""
    buf = BytesIO()
    doc = _document(buf, society, "Floor-wise housekeeping sheet", compress)
    width = doc.width
    printed = datetime.now(tz).strftime("%d %b %Y %H:%M")
    story: list = []
    for page in pages:
        staff, day = page["staff"], page["date"]
        shift = staff.shift
        shift_text = f"{shift.name} {_clock(shift.start_time)}–{_clock(shift.end_time)}" if shift else "—"
        for duty in page["duties"]:
            window = " – ".join(x for x in (_clock(duty.start_time), _clock(duty.end_time)) if x)
            for wing in wings:
                if story:
                    story.append(PageBreak())
                story += _floor_page(
                    society, width, printed, title=duty.duty_name,
                    who_rows=[
                        [_p("Name", "label"), _p(f"{staff.full_name} ({staff.employee_code})", "bold"),
                         _p("Date", "label"), _p(f"{day:%a, %d %b %Y}", "bold")],
                        [_p("Wing", "label"), _p(wing["label"], "bold"),
                         _p("Shift", "label"), _p(" · ".join(x for x in (shift_text, window) if x), "body")],
                    ],
                    columns=_columns(duty.checklist_items), wing=wing,
                    footer=f"Sheet {staff.employee_code}-{day:%Y%m%d}-{wing['label']}")
    doc.build(story)
    return buf.getvalue()


def render_blank_floor_sheet(society, tz: ZoneInfo, template, wings: List[dict], *, compress: bool = True) -> bytes:
    """A template as a floor-wise sheet with the name, date and times left blank; one page per wing."""
    buf = BytesIO()
    doc = _document(buf, society, template.name, compress)
    width = doc.width
    printed = datetime.now(tz).strftime("%d %b %Y %H:%M")
    story: list = []
    for wing in wings:
        if story:
            story.append(PageBreak())
        story += _floor_page(
            society, width, printed, title=template.name,
            who_rows=[
                [_p("Name", "label"), "", _p("Date", "label"), ""],
                [_p("Wing", "label"), _p(wing["label"], "bold"), _p("Shift", "label"), ""],
            ],
            columns=_columns(template.items), wing=wing, footer=wing["label"])
    doc.build(story)
    return buf.getvalue()
