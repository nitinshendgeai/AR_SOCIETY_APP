"""Certificate / NOC in Hindi or Marathi.

reportlab (used for every other PDF here) cannot shape Devanagari — conjuncts and vowel signs come out broken — so
these are drawn with fpdf2 and HarfBuzz text shaping, using the bundled Noto Sans Devanagari (SIL OFL)."""
from datetime import date
from pathlib import Path

from fpdf import FPDF

from app.modules.billing.services.bill_pdf import _d, flat_label
from app.modules.certificates.models.certificates import CertificateRequest
from app.modules.certificates.services.certificate_text import LANGUAGES, TEXT

FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"
BAND = (217, 217, 217)
RED = (192, 71, 75)
INK = (17, 17, 17)


def supported(lang: str) -> bool:
    return lang in LANGUAGES


def _party(t: dict, key: str, party: str) -> str:
    return t[key].format(party=party) if party else ""


def generate_deva_certificate_pdf(req: CertificateRequest, society, flat, lang: str) -> bytes:
    t = TEXT[lang]
    soc = society.name if society else "Society"
    issued = req.decided_on or date.today()
    party = (req.party_name or "").strip()
    values = {"name": req.applicant_name, "society": soc, "flat": flat_label(flat)}

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=14)
    pdf.add_font("Deva", "", str(FONTS / "NotoSansDevanagari-Regular.ttf"))
    pdf.add_font("Deva", "B", str(FONTS / "NotoSansDevanagari-SemiBold.ttf"))
    pdf.set_text_shaping(True)
    pdf.set_title(req.certificate_no or "Certificate")
    pdf.add_page()
    pdf.set_margins(18, 14, 18)
    pdf.set_text_color(*INK)
    width = pdf.w - 36

    # letterhead band over a red rule
    lines = [soc]
    address = ", ".join(x for x in [(society.address or "").strip() if society else "",
                                    society.city if society else None, society.state if society else None] if x)
    if society and society.pincode:
        address = f"{address} {society.pincode}".strip()
    if society and society.registration_number:
        lines.append(f"{t['regn']} {society.registration_number}")
    if address:
        lines.append(address)
    pdf.set_fill_color(*BAND)
    pdf.set_xy(18, 14)
    pdf.set_font("Deva", "B", 16)
    pdf.cell(width, 11, lines[0], align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Deva", "", 9.5)
    for extra in lines[1:]:
        pdf.cell(width, 5.5, extra, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(width, 2, "", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*RED)
    pdf.set_line_width(0.9)
    y = pdf.get_y()
    pdf.line(18, y, 18 + width, y)

    pdf.ln(12)
    pdf.set_font("Deva", "B", 14)
    pdf.multi_cell(width, 8, t["titles"][req.kind], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Deva", "", 10.5)
    pdf.cell(width * 0.6, 7, f"{t['number']}: {req.certificate_no or '-'}")
    pdf.cell(width * 0.4, 7, f"{t['date']}: {_d(issued)}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(7)

    def para(text: str, gap: float = 4) -> None:
        pdf.set_font("Deva", "", 11)
        pdf.multi_cell(width, 8, text, markdown=True, align="J", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(gap)

    if req.kind == "address_proof":
        para(t["address_only"].format(**values))
    else:
        para(t["member"].format(**values))
        body = t["bodies"][req.kind].format(
            party_in_favour=_party(t, "party_in_favour", party), party_to=_party(t, "party_to", party),
            party_from=_party(t, "party_from", party))
        if body:
            para(body)
    if req.kind in ("noc_sale", "noc_rent", "noc_loan", "no_dues"):
        dues = float(req.dues_at_decision or 0)
        para(t["dues_clear"].format(date=_d(issued)) if dues <= 0
             else t["dues_open"].format(date=_d(issued), amount=f"{dues:,.2f}"))
    if req.purpose:
        para(t["purpose"].format(purpose=req.purpose))
    para(t["footer"], gap=0)

    # sign-off
    pdf.ln(22)
    x = 18 + width * 0.5
    pdf.set_font("Deva", "", 9)
    pdf.set_x(18)
    pdf.cell(width * 0.5, 6, t["seal"])
    pdf.set_font("Deva", "B", 10)
    pdf.cell(width * 0.5, 6, t["for"].format(society=soc), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(*INK)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(x + 6, y, 18 + width, y)
    pdf.set_x(x)
    pdf.set_font("Deva", "", 8.5)
    pdf.cell(width * 0.5, 6, t["signatory"], align="C")
    return bytes(pdf.output())
