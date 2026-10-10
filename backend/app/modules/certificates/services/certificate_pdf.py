"""A4 certificate / NOC for an approved CertificateRequest, on the society's letterhead (same band as the bill and
receipt). Amounts print as "Rs." — the standard PDF fonts have no rupee glyph."""
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.billing.services.bill_pdf import S, _d, _p, flat_label, sign_off, society_header
from app.modules.certificates.models.certificates import CERTIFICATE_KINDS, CertificateRequest

_BODY = ParagraphStyle("cert_body", parent=S["cell"], fontSize=10.5, leading=17, alignment=TA_JUSTIFY)


def _what(req: CertificateRequest, society: str, flat: str) -> str:
    name, party = escape(req.applicant_name), escape(req.party_name or "")
    member = f"<b>{name}</b> is a member of <b>{escape(society)}</b> and occupies Flat No. <b>{escape(flat)}</b>"
    for_party = f" in favour of <b>{party}</b>" if party else ""
    if req.kind == "noc_sale":
        return (f"This is to certify that {member}. The member has informed the society of the intention to "
                f"sell / transfer the flat{for_party}. The society has <b>no objection</b> to the transfer, which is "
                f"subject to the transferee applying for membership and the transfer being recorded as required by "
                f"the society's bye-laws.")
    if req.kind == "noc_rent":
        return (f"This is to certify that {member}. The society has <b>no objection</b> to the member letting the "
                f"flat{for_party} on leave and licence, subject to the society's bye-laws, police verification and "
                f"the registration of the agreement with the society.")
    if req.kind == "noc_loan":
        return (f"This is to certify that {member}. The society has <b>no objection</b> to the member raising a loan"
                f"{' from <b>' + party + '</b>' if party else ''} against the flat by mortgage, subject to the "
                f"lender's charge being recorded with the society.")
    if req.kind == "noc_renovation":
        return (f"This is to certify that {member}. The society has <b>no objection</b> to the member carrying out "
                f"interior work in the flat, on condition that no structural change is made, work is done only "
                f"during the hours the society allows, and any damage to common areas is made good by the member.")
    if req.kind == "no_dues":
        return f"This is to certify that {member}."
    if req.kind == "address_proof":
        return (f"This is to certify that <b>{name}</b> resides at Flat No. <b>{escape(flat)}</b> of "
                f"<b>{escape(society)}</b>, as per the society's records.")
    return f"This is to certify that {member}."


def _dues_line(req: CertificateRequest, on: date) -> str:
    needs_clear = CERTIFICATE_KINDS[req.kind][2]
    if not needs_clear and req.kind != "no_dues":
        return ""
    dues = float(req.dues_at_decision or 0)
    if dues <= 0:
        return (f"As per the society's records, <b>no maintenance dues</b> are outstanding against the flat "
                f"as on {_d(on)}.")
    return (f"As per the society's records, dues of <b>Rs. {dues:,.2f}</b> were outstanding against the flat "
            f"as on {_d(on)}; this certificate is issued with the committee's approval.")


def generate_certificate_pdf(req: CertificateRequest, society, flat) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm, title=req.certificate_no or "Certificate")
    width = A4[0] - 36 * mm
    title, _, _ = CERTIFICATE_KINDS[req.kind]
    issued = req.decided_on or date.today()
    soc = society.name if society else "Society"

    story = list(society_header(society, width))
    story += [Spacer(1, 8 * mm), _p(title.upper(), "title"), Spacer(1, 6 * mm)]
    ref = Table([[_p(f"Certificate No.: <b>{escape(req.certificate_no or '-')}</b>", "cell"),
                  _p(f"Date: <b>{_d(issued)}</b>", "cell_r")]], colWidths=[width * 0.6, width * 0.4])
    ref.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [ref, Spacer(1, 8 * mm), Paragraph(_what(req, soc, flat_label(flat)), _BODY)]
    dues = _dues_line(req, issued)
    if dues:
        story += [Spacer(1, 4 * mm), Paragraph(dues, _BODY)]
    if req.purpose:
        story += [Spacer(1, 4 * mm), Paragraph(f"Purpose: {escape(req.purpose)}", _BODY)]
    story += [Spacer(1, 4 * mm),
              Paragraph("This certificate is issued at the member's request and does not by itself create any right "
                        "or liability on the society.", _BODY),
              Spacer(1, 22 * mm),
              sign_off(soc, width, "Seal of the society")]
    doc.build(story)
    return buf.getvalue()
