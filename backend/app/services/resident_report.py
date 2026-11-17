"""
The Residents report as the office prints or downloads it: the society's letterhead, the filters the list was showing,
and one line per resident with only the columns the person ticked, as a PDF or an Excel file.

Read-only: it formats rows the Residents list already returns. Identity numbers are never printed in full: only the last
four characters are shown, so a printout left on a desk does not hold a usable Aadhaar or PAN number.
"""
from datetime import date, datetime
from io import BytesIO
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, society_header

TYPE_WORDS = {"owner": "Owner", "co_owner": "Co-owner", "family": "Family", "dependent": "Dependent"}
COMM_WORDS = {"app_only": "App only", "sms": "SMS", "email": "Email", "whatsapp": "WhatsApp", "all": "All"}


def mask_id(number: Optional[str]) -> str:
    """'XXXXXXXX1234': the last four characters of an identity number, the rest hidden."""
    n = (number or "").strip()
    if not n:
        return ""
    return ("X" * max(len(n) - 4, 0)) + n[-4:]


def _id_proof(r: dict) -> str:
    kind = (r.get("id_proof_type") or "").strip()
    number = mask_id(r.get("id_proof_number"))
    return " ".join(p for p in (kind, number) if p)


# key -> (heading, weight for the width of the column, how to read it from a row, kind). `kind` 'date' is written to Excel
# as a real date; 'text' as text (so a phone number keeps its leading zeros).
COLUMNS: Dict[str, Tuple[str, float, Callable[[dict], object], str]] = {
    "flat":         ("Flat", 1.0, lambda r: r["flat"], "text"),
    "name":         ("Name", 2.4, lambda r: r["name"], "text"),
    "type":         ("Type", 1.1, lambda r: TYPE_WORDS.get(r["type"], r["type"]), "text"),
    "primary":      ("Primary contact", 1.0, lambda r: "Yes" if r["is_primary"] else "", "text"),
    "phone":        ("Mobile", 1.5, lambda r: r.get("phone") or "", "text"),
    "email":        ("Email", 2.6, lambda r: r.get("email") or "", "text"),
    "dob":          ("Date of birth", 1.3, lambda r: r.get("date_of_birth"), "date"),
    "move_in":      ("Moved in", 1.3, lambda r: r.get("move_in_date"), "date"),
    "move_out":     ("Moved out", 1.3, lambda r: r.get("move_out_date"), "date"),
    "kyc":          ("KYC", 1.0, lambda r: "Verified" if r["kyc_verified"] else "Not verified", "text"),
    "id_proof":     ("ID proof (last 4)", 2.0, _id_proof, "text"),
    "emergency":    ("Emergency contact", 2.2,
                     lambda r: " · ".join(p for p in (r.get("emergency_contact_name"), r.get("emergency_contact_phone")) if p),
                     "text"),
    "comm":         ("Notified by", 1.2, lambda r: COMM_WORDS.get(r.get("comm_preference") or "", ""), "text"),
    "family_count": ("Family members in flat", 1.3, lambda r: r.get("family_member_count") or 0, "number"),
    "status":       ("Status", 1.0, lambda r: "Active" if r["is_active"] else "Moved out", "text"),
}
DEFAULT_COLUMNS = ["flat", "name", "type", "phone", "email"]
# What the office would not expect on a printout unless asked for: only chosen on purpose.
SENSITIVE = ("id_proof", "dob", "emergency")


def catalog() -> List[dict]:
    """The columns that can be chosen, in the order they are offered, for the app's picker."""
    return [{"key": k, "label": v[0], "default": k in DEFAULT_COLUMNS, "sensitive": k in SENSITIVE}
            for k, v in COLUMNS.items()]


def choose_columns(requested: Optional[str]) -> List[str]:
    """The columns asked for, as a comma-separated list, in the catalogue's order. Empty: the default set. Unknown: error."""
    if requested is None or not requested.strip():
        return list(DEFAULT_COLUMNS)
    wanted = [c.strip() for c in requested.split(",") if c.strip()]
    unknown = [c for c in wanted if c not in COLUMNS]
    if unknown:
        raise ValueError("Unknown column: " + ", ".join(unknown))
    return [k for k in COLUMNS if k in wanted]


def cell_text(value) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d-%m-%Y")
    return str(value)


# ── PDF ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

_b = S["cell"]
P = {
    "title": ParagraphStyle("rr_title", parent=S["title"], fontSize=12.5, leading=15),
    "sub": ParagraphStyle("rr_sub", parent=S["centre_small"], fontSize=8.5),
    "th": ParagraphStyle("rr_th", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5),
    "td": ParagraphStyle("rr_td", parent=_b, fontSize=8, leading=9.8),
    "note": ParagraphStyle("rr_note", parent=_b, fontSize=7.8, leading=10, textColor=MUTED),
}


def render_residents_pdf(rows: List[dict], columns: Sequence[str], filters: List[str], society, *, compress: bool = True) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    wide = len(columns) > 5
    size = landscape(A4) if wide else portrait(A4)
    doc = SimpleDocTemplate(buf, pagesize=size, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=8 * mm,
                            bottomMargin=12 * mm, title="Residents Report", author=name, pageCompression=1 if compress else 0)
    sub = "Filters: " + ("; ".join(filters) if filters else "none (every resident on record)")
    story = [*society_header(society, doc.width), Spacer(1, 4 * mm), Paragraph("RESIDENTS REPORT", P["title"]),
             Paragraph(escape(sub), P["sub"]), Spacer(1, 3 * mm)]

    sr_w = 10 * mm
    weights = [COLUMNS[c][1] for c in columns]
    unit = (doc.width - sr_w) / sum(weights)
    widths = [sr_w] + [w * unit for w in weights]

    def para(text, style="td"):
        return Paragraph(escape(cell_text(text)), P[style])

    table = [[para("Sr.", "th")] + [Paragraph(escape(COLUMNS[c][0]), P["th"]) for c in columns]]
    for i, r in enumerate(rows, 1):
        table.append([para(i)] + [para(COLUMNS[c][2](r)) for c in columns])
    t = Table(table, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(escape(f"{len(rows)} resident{'' if len(rows) == 1 else 's'}"), P["note"]))
    if not rows:
        story.append(Paragraph("No resident matches these filters.", P["note"]))

    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · Residents Report")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ── Excel ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def render_residents_xlsx(rows: List[dict], columns: Sequence[str], filters: List[str], society) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Residents"
    name = society.name if society else "Society"
    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def put(row: int, col: int, value, *, bold=False, fmt: Optional[str] = None):
        cell = ws.cell(row=row, column=col)
        cell.value = value
        if isinstance(value, str):
            cell.data_type = "s"            # always text: a name or number starting with = + - @ must not become a formula
        if bold:
            cell.font = Font(bold=True)
        if fmt:
            cell.number_format = fmt
        return cell

    put(1, 1, name, bold=True)
    put(2, 1, "Residents report", bold=True)
    put(3, 1, "Filters: " + ("; ".join(filters) if filters else "none (every resident on record)"))
    put(4, 1, f"Printed {printed}")
    head_row = 6
    header_fill = PatternFill("solid", fgColor="EDEDED")
    for j, label in enumerate(["Sr."] + [COLUMNS[c][0] for c in columns], 1):
        cell = put(head_row, j, label, bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for i, r in enumerate(rows, 1):
        put(head_row + i, 1, i)
        for j, c in enumerate(columns, 2):
            value = COLUMNS[c][2](r)
            kind = COLUMNS[c][3]
            if kind == "date" and isinstance(value, (date, datetime)):
                put(head_row + i, j, value, fmt="DD-MM-YYYY")
            elif kind == "number":
                put(head_row + i, j, int(value or 0))
            else:
                put(head_row + i, j, "" if value is None else str(value))
    widths = [6] + [max(10, round(COLUMNS[c][1] * 9)) for c in columns]
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(row=head_row + 1, column=1)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
