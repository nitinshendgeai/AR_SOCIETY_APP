"""A5 pass card for a domestic help: society, name, kind, pass number, flats, validity and a QR of the pass number
(so a scanner or a phone camera can read it at the gate)."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable

from app.modules.billing.services.bill_pdf import S, _d, _p, society_header
from app.modules.gate.models.gate import DomesticHelp


class _QR(Flowable):
    def __init__(self, value: str, size: float):
        super().__init__()
        self.value, self.size = value, size
        self.width = self.height = size

    def draw(self):
        widget = qr.QrCodeWidget(self.value)
        x0, y0, x1, y1 = widget.getBounds()
        d = Drawing(self.size, self.size, transform=[self.size / (x1 - x0), 0, 0, self.size / (y1 - y0), 0, 0])
        d.add(widget)
        renderPDF.draw(d, self.canv, 0, 0)


def generate_pass_pdf(h: DomesticHelp, society, flats: list) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A5, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=10 * mm,
                            bottomMargin=10 * mm, title=h.pass_no or "Pass")
    width = A5[0] - 24 * mm
    rows = [
        ("Name", h.name), ("Work", h.kind.title()), ("Mobile", h.mobile),
        ("Works in", ", ".join(flats) or "-"),
        ("Valid till", _d(h.valid_until) if h.valid_until else "-"),
        ("Police verified", "Yes" if h.police_verified else "No"),
    ]
    info = Table([[_p(f"{k}", "small"), _p(f"<b>{escape(v)}</b>", "cell")] for k, v in rows],
                 colWidths=[28 * mm, width - 28 * mm - 40 * mm])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    body = Table([[info, _QR(h.pass_no or "", 36 * mm)]], colWidths=[width - 40 * mm, 40 * mm])
    body.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story = list(society_header(society, width)) + [
        Spacer(1, 6 * mm), _p("DOMESTIC HELP PASS", "title"), Spacer(1, 2 * mm),
        _p(f"Pass No. <b>{escape(h.pass_no or '-')}</b>", "centre"), Spacer(1, 6 * mm), body, Spacer(1, 8 * mm),
        _p("Carry this pass and show it at the gate. Entry and exit are recorded by security.", "centre_small"),
    ]
    doc.build(story)
    return buf.getvalue()
