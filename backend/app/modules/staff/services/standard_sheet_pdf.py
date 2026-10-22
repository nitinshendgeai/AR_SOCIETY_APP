"""A standard checklist printed as a blank sheet, in Hindi or English.

English goes through the same reportlab sheet as any template. reportlab cannot shape Devanagari (conjuncts and vowel
signs come out broken), so Hindi is drawn with fpdf2 and HarfBuzz text shaping using the bundled Noto Sans Devanagari
(SIL OFL), the same way the Hindi certificates are. Both lay out one A4 page: the letterhead, the name / date block, the
in and out times, the checks with a tick box and remarks column, and signature lines."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fpdf import FPDF

from app.modules.staff.models.staff import StaffDepartment
from app.modules.staff.services import duty_sheet_pdf
from app.modules.staff.services.standard_checklists import BY_CODE
from app.modules.staff.services.standard_checklists_hi import DEPARTMENTS, HINDI, LABELS

FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"
BAND = (217, 217, 217)
HEAD = (239, 239, 239)
RED = (192, 71, 75)
INK = (17, 17, 17)
MUTED = (85, 85, 85)
RULE = (150, 150, 150)
LEFT = 18
ROW_MIN = 13


def languages() -> tuple:
    return ("en", "hi")


def english_sheet(society, tz: ZoneInfo, code: str) -> bytes:
    c = BY_CODE[code]
    template = SimpleNamespace(
        name=c["name"], description=c["description"], department=StaffDepartment(c["department"]),
        items=[SimpleNamespace(sequence=i, title=t, description=d, is_required=r)
               for i, (t, d, r) in enumerate(c["items"])])
    return duty_sheet_pdf.render_blank_template_sheet(society, tz, template)


def _letterhead(pdf: FPDF, society, width: float) -> None:
    name = (society.name if society else None) or "Society"
    address = ", ".join(x for x in [(society.address or "").strip() if society else "",
                                    society.city if society else None, society.state if society else None] if x)
    if society and society.pincode:
        address = f"{address} {society.pincode}".strip()
    pdf.set_fill_color(*BAND)
    pdf.set_xy(LEFT, 12)
    pdf.set_font("Deva", "B", 15)
    pdf.cell(width, 9, name, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    if address:
        pdf.set_font("Deva", "", 8.5)
        pdf.cell(width, 5, address, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(width, 1.5, "", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*RED)
    pdf.set_line_width(0.8)
    y = pdf.get_y()
    pdf.line(LEFT, y, LEFT + width, y)


def _box(pdf: FPDF, x: float, y: float, w: float, h: float, text: str = "", *, bold: bool = False,
         fill=None, align: str = "L", size: float = 9) -> None:
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.3)
    if fill:
        pdf.set_fill_color(*fill)
    pdf.rect(x, y, w, h, style="DF" if fill else "D")
    if text:
        pdf.set_font("Deva", "B" if bold else "", size)
        pdf.set_xy(x + 1, y)
        pdf.cell(w - 2, h, text, align=align)


def hindi_sheet(society, tz: ZoneInfo, code: str) -> bytes:
    english, hindi = BY_CODE[code], HINDI[code]
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=10)
    pdf.add_font("Deva", "", str(FONTS / "NotoSansDevanagari-Regular.ttf"))
    pdf.add_font("Deva", "B", str(FONTS / "NotoSansDevanagari-SemiBold.ttf"))
    pdf.set_text_shaping(True)
    pdf.set_title(hindi["name"])
    pdf.add_page()
    pdf.set_margins(LEFT, 10, LEFT)
    pdf.set_text_color(*INK)
    width = pdf.w - 2 * LEFT

    _letterhead(pdf, society, width)
    pdf.ln(3)
    pdf.set_font("Deva", "B", 13)
    pdf.cell(width, 7, hindi["name"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Deva", "", 8.2)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(width, 4.2, LABELS["hint"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(1.5)

    # name / date, department / shift
    y = pdf.get_y()
    lw, vw = width * 0.14, width * 0.36
    for r, (a, av, b, bv) in enumerate([
        (LABELS["name"], "", LABELS["date"], ""),
        (LABELS["department"], DEPARTMENTS.get(english["department"], english["department"]), LABELS["shift"], ""),
    ]):
        yy = y + r * 8
        _box(pdf, LEFT, yy, lw, 8, a, fill=BAND, size=8.5)
        _box(pdf, LEFT + lw, yy, vw, 8, av)
        _box(pdf, LEFT + lw + vw, yy, lw, 8, b, fill=BAND, size=8.5)
        _box(pdf, LEFT + 2 * lw + vw, yy, vw, 8, bv)
    y += 16 + 2

    # in / out / staff signature
    cols = [(0.13, LABELS["in"], True), (0.15, "", False), (0.13, LABELS["out"], True), (0.15, "", False),
            (0.17, LABELS["staff_sign"], True), (0.27, "", False)]
    x = LEFT
    for frac, text, shaded in cols:
        _box(pdf, x, y, width * frac, 9.5, text, fill=BAND if shaded else None, size=8)
        x += width * frac
    y += 9.5 + 3

    # checks
    nw, dw, rw = 9.0, 17.0, 40.0
    cw = width - nw - dw - rw
    _box(pdf, LEFT, y, width, 7, hindi["name"], bold=True, fill=BAND, size=9.5)
    y += 7
    x = LEFT
    for w, text in ((nw, LABELS["number"]), (cw, LABELS["check"]), (dw, LABELS["done"]), (rw, LABELS["remarks"])):
        _box(pdf, x, y, w, 6, text, bold=True, fill=HEAD, align="C", size=8.2)
        x += w
    y += 6
    for n, ((title, note), (_, _, required)) in enumerate(zip(hindi["items"], english["items"]), 1):
        heading = title + (" *" if required else "")
        pdf.set_font("Deva", "", 8.6)
        lines = pdf.multi_cell(cw - 2, 4.0, note, split_only=True)
        h = max(ROW_MIN, 5.4 + 4.0 * len(lines) + 1.6)
        _box(pdf, LEFT, y, nw, h, str(n), align="C", size=8)
        _box(pdf, LEFT + nw, y, cw, h)
        _box(pdf, LEFT + nw + cw, y, dw, h)
        _box(pdf, LEFT + nw + cw + dw, y, rw, h)
        pdf.set_xy(LEFT + nw + 1, y + 0.8)
        pdf.set_font("Deva", "B", 9)
        pdf.cell(cw - 2, 4.6, heading, new_x="LEFT", new_y="NEXT")
        pdf.set_x(LEFT + nw + 1)
        pdf.set_font("Deva", "", 8.6)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(cw - 2, 4.0, note, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*INK)
        # a tick box to mark in the "done" column
        pdf.set_draw_color(*INK)
        pdf.set_line_width(0.4)
        pdf.rect(LEFT + nw + cw + dw / 2 - 2.5, y + h / 2 - 2.5, 5, 5)
        y += h

    # supervisor remarks and signatures
    y += 4
    _box(pdf, LEFT, y, width, 5, LABELS["supervisor_remarks"], size=8, fill=None)
    _box(pdf, LEFT, y + 5, width, 11)
    y += 16 + 9
    pdf.set_draw_color(*INK)
    pdf.set_line_width(0.4)
    gap = width * 0.03
    spans = [(width * 0.35, LABELS["staff_sign"]), (width * 0.35, LABELS["supervisor_sign"]), (width * 0.24, LABELS["date"])]
    x = LEFT
    for w, text in spans:
        pdf.line(x, y, x + w, y)
        pdf.set_xy(x, y + 0.5)
        pdf.set_font("Deva", "", 7.8)
        pdf.set_text_color(*MUTED)
        pdf.cell(w, 4.5, text)
        x += w + gap
    pdf.set_text_color(*MUTED)
    pdf.set_font("Deva", "", 7.2)
    pdf.set_xy(LEFT, y + 7)
    pdf.cell(width, 4, f"{LABELS['printed']} {datetime.now(tz).strftime('%d %b %Y %H:%M')} IST")
    return bytes(pdf.output())


def render(society, tz: ZoneInfo, code: str, lang: str) -> bytes:
    return hindi_sheet(society, tz, code) if lang == "hi" else english_sheet(society, tz, code)
