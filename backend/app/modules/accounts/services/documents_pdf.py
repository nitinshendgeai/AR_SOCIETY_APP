"""
The books' documents printed the way a housing society files them:

- a voucher (Receipt, Payment, Journal, Contra…) on half a sheet (A5
  landscape): the society's letterhead, the voucher's number and date, its
  Dr/Cr lines, the amount in words, the narration and signature boxes —
  Prepared by, Checked by, the authorising office bearer and, on a payment,
  the receiver;
- a ledger account (or a member's / vendor's account) for a period: opening
  balance, each posting with the running balance, totals and the closing
  balance;
- the day book: every voucher of a period with its lines;
- the members' ledger: each flat's balance, dues and advances totalled.

The built-in PDF fonts have no rupee sign, so amounts are headed "Rs.".
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import List, Optional
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.modules.billing.services.bill_pdf import INK, MUTED, RULE, S, _inr, amount_in_words, society_header

_b = S["cell"]
P = {
    "title": ParagraphStyle("doc_title", parent=S["title"], fontSize=12, leading=15),
    "sub": ParagraphStyle("doc_sub", parent=S["centre_small"], fontSize=8.5),
    "th": ParagraphStyle("doc_th", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5),
    "th_r": ParagraphStyle("doc_th_r", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.5, alignment=2),
    "td": ParagraphStyle("doc_td", parent=_b, fontSize=8, leading=9.8),
    "td_b": ParagraphStyle("doc_td_b", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.8),
    "td_r": ParagraphStyle("doc_td_r", parent=_b, fontSize=8, leading=9.8, alignment=2),
    "td_rb": ParagraphStyle("doc_td_rb", parent=_b, fontName="Helvetica-Bold", fontSize=8, leading=9.8,
                            alignment=2),
    "td_small": ParagraphStyle("doc_td_small", parent=_b, fontSize=7.2, leading=8.8, textColor=MUTED),
    "cell": ParagraphStyle("doc_cell", parent=_b, fontSize=8.8, leading=11),
    "cell_r": ParagraphStyle("doc_cell_r", parent=_b, fontSize=8.8, leading=11, alignment=2),
    "note": ParagraphStyle("doc_note", parent=_b, fontSize=7.8, leading=10, textColor=MUTED),
    "sign": ParagraphStyle("doc_sign", parent=S["sign"], fontSize=7.8),
    "sign_name": ParagraphStyle("doc_sign_name", parent=S["sign"], fontSize=7.5, textColor=MUTED),
    "cancelled": ParagraphStyle("doc_cancelled", parent=_b, fontName="Helvetica-Bold", fontSize=9,
                                textColor=colors.HexColor("#B91C1C")),
}
GREY = colors.HexColor("#EDEDED")
STRUCK = colors.HexColor("#9A9A9A")


def _p(text, style: str = "td") -> Paragraph:
    return Paragraph(escape(str(text)) if text is not None else "", P[style])


def _amt(v) -> str:
    """'' for nothing, else 1,234.00."""
    return "" if v in (None, "") or Decimal(v) == 0 else _inr(v)


def _drcr(v) -> str:
    """A signed balance as '1,234.00 Dr' / 'Cr'; 'Nil' for zero."""
    d = Decimal(v or 0)
    if d == 0:
        return "Nil"
    return f"{_inr(abs(d))} {'Dr' if d > 0 else 'Cr'}"


def _date(v) -> str:
    if not v:
        return ""
    d = v if isinstance(v, date) else date.fromisoformat(str(v)[:10])
    return d.strftime("%d-%m-%Y")


def period_label(date_from: Optional[date], date_to: Optional[date]) -> str:
    if date_from and date_to:
        return f"From {_date(date_from)} to {_date(date_to)}"
    if date_from:
        return f"From {_date(date_from)}"
    if date_to:
        return f"Up to {_date(date_to)}"
    return "All dates"


def _doc(buf, pagesize, title: str, author: str, compress: bool, margins=(10, 10, 8, 12)):
    left, right, top, bottom = margins
    return SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=left * mm, rightMargin=right * mm,
                             topMargin=top * mm, bottomMargin=bottom * mm, title=title, author=author,
                             pageCompression=1 if compress else 0)


def _footer(name: str, label: str):
    printed = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y %H:%M IST")

    def draw(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc_.leftMargin, 6 * mm, f"{name} · {label}")
        canvas.drawRightString(doc_.leftMargin + doc_.width, 6 * mm, f"Printed {printed} · Page {doc_.page}")
        canvas.restoreState()
    return draw


def _grid(rows, widths, *, total_rows: int = 0, extra=()) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if total_rows:
        style.append(("LINEABOVE", (0, -total_rows), (-1, -total_rows), 0.8, INK))
    t.setStyle(TableStyle(style + list(extra)))
    return t


def _signature_boxes(titles: List[str], names: List[str], width: float) -> Table:
    """Signature lines side by side, with gaps so each reads as its own
    line; a name (who prepared it) printed small above its line."""
    gap = 8 * mm
    col = (width - gap * (len(titles) - 1)) / len(titles)
    widths = [w for _ in titles for w in (col, gap)][:-1]

    def spread(cells):
        return [x for c in cells for x in (c, "")][:-1]
    rows = [spread([_p(n, "sign_name") for n in names]), spread([_p(t, "sign") for t in titles])]
    t = Table(rows, colWidths=widths, rowHeights=[12 * mm, None])
    t.setStyle(TableStyle(
        [("LINEABOVE", (2 * i, 1), (2 * i, 1), 0.8, INK) for i in range(len(titles))]
        + [("VALIGN", (0, 0), (-1, 0), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _for_society(name: str, office: str) -> Table:
    sign = Table([[_p(f"For {name.upper()}", "sign")], [Spacer(1, 10 * mm)], [_p(office, "sign")]],
                 colWidths=[70 * mm], hAlign="RIGHT")
    sign.setStyle(TableStyle([("LINEABOVE", (0, 2), (0, 2), 0.8, INK)]))
    return sign


# ── Voucher ───────────────────────────────────────────────────────────────────

_SIGNATURES = {
    "payment": ["Prepared by", "Checked by", "Hon. Secretary / Treasurer", "Receiver's Signature"],
    "receipt": ["Prepared by", "Checked by", "Hon. Treasurer"],
}


def _line_particulars(e: dict) -> str:
    tag = e.get("flat_label") or e.get("vendor_name")
    return f"{e['account_name']} — {tag}" if tag else (e.get("account_name") or "")


def _party(v: dict) -> Optional[tuple]:
    """('Paid to', who) on a payment, ('Received from', who) on a receipt:
    the vendor or flat on the other side of cash/bank, else that ledger."""
    side = {"payment": "debit", "receipt": "credit"}.get(v["voucher_type"])
    if not side:
        return None
    lines = [e for e in v["entries"] if Decimal(e[side] or 0) > 0]
    names = list(dict.fromkeys(_line_particulars(e) for e in lines))
    return ("Paid to" if side == "debit" else "Received from", ", ".join(names))


def render_voucher_pdf(v: dict, society, *, compress: bool = True) -> bytes:
    """`v`: a voucher as the API returns it."""
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = _doc(buf, landscape(A5), f"Voucher {v['voucher_number']}", name, compress, margins=(10, 10, 8, 10))
    width = doc.width
    story = [*society_header(society, width), Spacer(1, 3 * mm)]

    title = f"{v['voucher_type_label'].upper()} VOUCHER"
    head = Table([[
        Paragraph(f"No.: <b>{escape(v['voucher_number'])}</b>", P["cell"]),
        Paragraph(f"<u>{escape(title)}</u>", P["title"]),
        Paragraph(f"Date: <b>{_date(v['voucher_date'])}</b>", P["cell_r"]),
    ]], colWidths=[width * 0.3, width * 0.4, width * 0.3])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 2 * mm)]
    party = _party(v)
    if party:
        story += [Paragraph(f"{party[0]}: <b>{escape(party[1])}</b>", P["cell"]), Spacer(1, 2 * mm)]

    amount_w = 30 * mm
    rows = [[_p("Particulars", "th"), _p("Debit Rs.", "th_r"), _p("Credit Rs.", "th_r")]]
    for e in v["entries"]:
        dr = Decimal(e["debit"] or 0) > 0
        cell = [Paragraph(f"{'' if dr else 'To '}{escape(_line_particulars(e))}"
                          f"{' &nbsp;Dr' if dr else ''}", P["td_b" if dr else "td"])]
        if e.get("narration"):
            cell.append(_p(e["narration"], "td_small"))
        rows.append([cell, _p(_amt(e["debit"]), "td_r"), _p(_amt(e["credit"]), "td_r")])
    rows.append([_p("Total", "td_b"), _p(_inr(v["amount"]), "td_rb"), _p(_inr(v["amount"]), "td_rb")])
    story.append(_grid(rows, [width - 2 * amount_w, amount_w, amount_w], total_rows=1))

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"Amount in words: <b>{escape(amount_in_words(v['amount']))}</b>", P["cell"]))
    if v.get("narration"):
        story.append(Paragraph(f"Narration: {escape(v['narration'])}", P["cell"]))
    if v.get("reference"):
        story.append(Paragraph(f"Reference: {escape(v['reference'])}", P["cell"]))
    if v.get("is_cancelled"):
        story += [Spacer(1, 1.5 * mm),
                  _p(f"CANCELLED{': ' + v['cancel_reason'] if v.get('cancel_reason') else ''}", "cancelled")]
    if v.get("edited_at"):
        when = datetime.fromisoformat(v["edited_at"]).strftime("%d-%m-%Y")
        story.append(_p(f"Revised on {when}{' by ' + v['edited_by_name'] if v.get('edited_by_name') else ''}"
                        f" ({len(v.get('revisions') or [])} earlier version(s) on record).", "note"))

    titles = _SIGNATURES.get(v["voucher_type"], ["Prepared by", "Checked by", "Hon. Secretary / Treasurer"])
    names = [v.get("created_by_name") or ""] + [""] * (len(titles) - 1)
    story += [Spacer(1, 4 * mm), KeepTogether([_signature_boxes(titles, names, width)])]
    doc.build(story)
    return buf.getvalue()


# ── Ledger account ────────────────────────────────────────────────────────────

def render_ledger_pdf(st: dict, society, *, title: Optional[str] = None, compress: bool = True) -> bytes:
    """`st`: a ledger statement as the API returns it. `title`: the account
    shown (a member's or vendor's), if not the ledger itself."""
    buf = BytesIO()
    name = society.name if society else "Society"
    account = st["account"]
    heading = title or account["name"]
    doc = _doc(buf, A4, f"Ledger - {heading}", name, compress)
    width = doc.width
    period = period_label(st.get("date_from") and date.fromisoformat(st["date_from"]),
                          st.get("date_to") and date.fromisoformat(st["date_to"]))
    sub = f"{account['name']} ({account['group_name']}) · {period}" if title else \
        f"{account.get('group_name') or ''} · {period}".strip(" ·")
    story = [*society_header(society, width), Spacer(1, 4 * mm),
             Paragraph(escape(f"LEDGER ACCOUNT — {heading.upper()}"), P["title"]),
             _p(sub, "sub"), Spacer(1, 3 * mm)]

    rows = [[_p("Date", "th"), _p("Voucher No.", "th"), _p("Particulars", "th"), _p("Debit Rs.", "th_r"),
             _p("Credit Rs.", "th_r"), _p("Balance Rs.", "th_r")]]
    rows.append([_p(_date(st.get("date_from")) or "", "td"), "", _p("Opening Balance", "td_b"), "", "",
                 _p(_drcr(st["opening"]), "td_rb")])
    for l in st["lines"]:
        cell = [_p(l["particulars"], "td")]
        if l.get("narration"):
            cell.append(_p(l["narration"], "td_small"))
        rows.append([_p(_date(l["date"])), _p(l["voucher_number"]), cell, _p(_amt(l["debit"]), "td_r"),
                     _p(_amt(l["credit"]), "td_r"), _p(_drcr(l["balance"]), "td_r")])
    if not st["lines"]:
        rows.append(["", "", _p("No entries in this period.", "note"), "", "", ""])
    rows.append(["", "", _p("Total", "td_b"), _p(_inr(st["total_debit"]), "td_rb"),
                 _p(_inr(st["total_credit"]), "td_rb"), ""])
    rows.append([_p(_date(st.get("date_to")) or "", "td"), "", _p("Closing Balance", "td_b"), "", "",
                 _p(_drcr(st["closing"]), "td_rb")])
    fixed = [19 * mm, 30 * mm, 0, 25 * mm, 25 * mm, 29 * mm]
    fixed[2] = width - sum(fixed)
    story.append(_grid(rows, fixed, total_rows=2))
    story += [Spacer(1, 12 * mm), KeepTogether([_for_society(name, "Hon. Treasurer")])]
    doc.build(story, onFirstPage=_footer(name, f"Ledger: {heading}"),
              onLaterPages=_footer(name, f"Ledger: {heading}"))
    return buf.getvalue()


# ── Day book ──────────────────────────────────────────────────────────────────

def render_day_book_pdf(vouchers: List[dict], society, date_from: Optional[date], date_to: Optional[date],
                        *, type_label: Optional[str] = None, compress: bool = True) -> bytes:
    """`vouchers`: as the API returns them, oldest first. Cancelled ones are
    shown struck out and left out of the totals."""
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = _doc(buf, A4, "Day Book", name, compress)
    width = doc.width
    sub = period_label(date_from, date_to) + (f" · {type_label} vouchers" if type_label else "")
    story = [*society_header(society, width), Spacer(1, 4 * mm), Paragraph("DAY BOOK", P["title"]),
             _p(sub, "sub"), Spacer(1, 3 * mm)]

    rows = [[_p("Date", "th"), _p("Voucher No.", "th"), _p("Particulars", "th"), _p("Debit Rs.", "th_r"),
             _p("Credit Rs.", "th_r")]]
    extra, total = [], Decimal(0)
    for v in vouchers:
        cancelled = v.get("is_cancelled")
        first = len(rows)
        for i, e in enumerate(v["entries"]):
            dr = Decimal(e["debit"] or 0) > 0
            rows.append([
                _p(_date(v["voucher_date"])) if i == 0 else "",
                [_p(v["voucher_number"]), _p(v["voucher_type_label"], "td_small")] if i == 0 else "",
                Paragraph(f"{'' if dr else '&nbsp;&nbsp;&nbsp;To '}{escape(_line_particulars(e))}"
                          f"{' &nbsp;Dr' if dr else ''}", P["td"]),
                _p(_amt(e["debit"]), "td_r"), _p(_amt(e["credit"]), "td_r"),
            ])
        note = v.get("narration") or ""
        if cancelled:
            note = f"CANCELLED{': ' + v['cancel_reason'] if v.get('cancel_reason') else ''}" + \
                (f" · {note}" if note else "")
        if note:
            rows.append(["", "", _p(f"({note})", "td_small"), "", ""])
        last = len(rows) - 1
        extra.append(("LINEBELOW", (0, last), (-1, last), 0.6, RULE))
        if cancelled:
            extra.append(("TEXTCOLOR", (0, first), (-1, last), STRUCK))
        else:
            total += Decimal(v["amount"])
    if not vouchers:
        rows.append(["", "", _p("No vouchers in this period.", "note"), "", ""])
    live = sum(1 for v in vouchers if not v.get("is_cancelled"))
    rows.append(["", "", _p(f"Total ({live} vouchers)", "td_b"), _p(_inr(total), "td_rb"), _p(_inr(total), "td_rb")])
    fixed = [19 * mm, 32 * mm, 0, 26 * mm, 26 * mm]
    fixed[2] = width - sum(fixed)
    t = Table(rows, colWidths=fixed, repeatRows=1)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, INK), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("LINEAFTER", (0, 0), (-2, -1), 0.3, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), GREY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ] + extra))
    story.append(t)
    doc.build(story, onFirstPage=_footer(name, "Day Book"), onLaterPages=_footer(name, "Day Book"))
    return buf.getvalue()


# ── Members' ledger ───────────────────────────────────────────────────────────

def render_members_ledger_pdf(members: List[dict], society, as_of: date, *, compress: bool = True) -> bytes:
    """`members`: [{flat_label, member_name, balance (signed: Dr owes)}]."""
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = _doc(buf, A4, "Members' Ledger", name, compress)
    width = doc.width
    story = [*society_header(society, width), Spacer(1, 4 * mm),
             Paragraph(escape(f"MEMBERS' LEDGER — BALANCES AS ON {_date(as_of)}"), P["title"]),
             _p("Each flat's account with the society: Dr — dues receivable, Cr — paid in advance", "sub"),
             Spacer(1, 3 * mm)]
    rows = [[_p("Sr.", "th"), _p("Flat", "th"), _p("Member", "th"), _p("Dues (Dr) Rs.", "th_r"),
             _p("Advance (Cr) Rs.", "th_r")]]
    dues = advance = Decimal(0)
    for i, m in enumerate(members, 1):
        bal = Decimal(m["balance"])
        dues += max(bal, Decimal(0))
        advance += max(-bal, Decimal(0))
        rows.append([_p(i), _p(m["flat_label"]), _p(m["member_name"]),
                     _p(_amt(bal) if bal > 0 else "", "td_r"), _p(_amt(-bal) if bal < 0 else "", "td_r")])
    rows.append(["", _p("TOTAL", "td_b"), _p(f"{len(members)} flats", "td"), _p(_inr(dues), "td_rb"),
                 _p(_inr(advance), "td_rb")])
    rows.append(["", _p("NET", "td_b"), _p("Receivable from members (net of advances)", "td"), "",
                 _p(_drcr(dues - advance), "td_rb")])
    fixed = [12 * mm, 28 * mm, 0, 32 * mm, 32 * mm]
    fixed[2] = width - sum(fixed)
    story.append(_grid(rows, fixed, total_rows=2))
    story += [Spacer(1, 12 * mm), KeepTogether([_for_society(name, "Hon. Treasurer")])]
    doc.build(story, onFirstPage=_footer(name, "Members' Ledger"), onLaterPages=_footer(name, "Members' Ledger"))
    return buf.getvalue()
