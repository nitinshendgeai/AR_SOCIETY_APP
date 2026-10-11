"""
The registers printed on landscape A4: the society's letterhead, the register's name and period, a ruled table with
the name of whoever made each entry, totals, and signature lines. Amounts are headed "Rs." (the built-in PDF fonts
have no rupee sign).
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import List, Optional, Sequence, Tuple

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer
from xml.sax.saxutils import escape

from app.modules.accounts.services.documents_pdf import (
    P, _amt, _date, _doc, _drcr, _footer, _for_society, _grid, _p, period_label,
)
from app.modules.billing.services.bill_pdf import _inr, society_header

# (heading, key, width in mm — 0 takes the rest, right-aligned?)
Column = Tuple[str, str, float, bool]

_STATUS = {"issued": "Issued", "generated": "Generated", "partially_paid": "Part paid", "paid": "Paid",
           "overdue": "Overdue", "cancelled": "Cancelled", "unpaid": "Unpaid", "part_paid": "Part paid"}


def _table(rows: Sequence[dict], columns: Sequence[Column], width: float, total_cells: Optional[List[str]] = None):
    head = [_p(h, "th_r" if right else "th") for h, _k, _w, right in columns]
    body = [head]
    for r in rows:
        body.append([_p(r.get(k), "td_r" if right else "td") for _h, k, _w, right in columns])
    if not rows:
        body.append([_p("No entries in this period.", "note")] + [""] * (len(columns) - 1))
    if total_cells:
        body.append([_p(c, "td_rb" if columns[i][3] else "td_b") for i, c in enumerate(total_cells)])
    widths = [w * mm for _h, _k, w, _r in columns]
    widths = [w or 0 for w in widths]
    free = width - sum(widths)
    widths = [w if w else free for w in widths] if 0 in widths else widths
    return _grid(body, widths, total_rows=1 if total_cells else 0)


def _build(title: str, sub: str, society, story_parts, signatures: bool = True) -> bytes:
    buf = BytesIO()
    name = society.name if society else "Society"
    doc = _doc(buf, landscape(A4), title, name, True)
    story = [*society_header(society, doc.width), Spacer(1, 3 * mm), Paragraph(escape(title.upper()), P["title"]),
             _p(sub, "sub"), Spacer(1, 3 * mm)]
    for part in story_parts(doc.width):
        story.append(part)
    if signatures:
        story += [Spacer(1, 10 * mm), KeepTogether([_for_society(name, "Hon. Treasurer")])]
    footer = _footer(name, title)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def render_cash_bank_pdf(book: dict, society, *, compress: bool = True) -> bytes:
    period = period_label(book["date_from"] and date.fromisoformat(book["date_from"]),
                          book["date_to"] and date.fromisoformat(book["date_to"]))
    columns: List[Column] = [
        ("Date", "date", 19, False), ("Voucher No.", "voucher_number", 29, False), ("Particulars", "particulars", 0, False),
        ("Entered by", "entered_by", 32, False), ("Approved by", "approved_by", 32, False),
        ("Receipts Rs.", "receipt", 26, True), ("Payments Rs.", "payment", 26, True), ("Balance Rs.", "balance", 30, True),
    ]

    def parts(width):
        out = []
        for i, s in enumerate(book["sections"]):
            if i:
                out.append(PageBreak())
            label = f"{s['account_name']} ({'Cash' if s['kind'] == 'cash' else 'Bank'})"
            out += [Paragraph(escape(label), P["title"]), Spacer(1, 1.5 * mm)]
            rows = [{"date": "", "voucher_number": "", "particulars": "Opening balance", "entered_by": "",
                     "approved_by": "", "receipt": "", "payment": "", "balance": _drcr(s["opening"])}]
            for l in s["lines"]:
                rows.append({
                    "date": _date(l["date"]), "voucher_number": l["voucher_number"],
                    "particulars": l["particulars"] + (f" — {l['narration']}" if l.get("narration") else ""),
                    "entered_by": l["entered_by"] or "", "approved_by": l["approved_by"] or ("Auto-posted" if l["is_auto"] else ""),
                    "receipt": _amt(l["receipt"]), "payment": _amt(l["payment"]), "balance": _drcr(l["balance"]),
                })
            total = ["", "", "Total · Closing balance", "", "", _inr(s["receipts"]), _inr(s["payments"]), _drcr(s["closing"])]
            out += [_table(rows, columns, width, total), Spacer(1, 4 * mm)]
        if not book["sections"]:
            out.append(_p("No cash or bank accounts.", "note"))
        return out

    return _build("Cash and Bank Book", period, society, parts)


def render_invoice_register_pdf(reg: dict, society, *, compress: bool = True) -> bytes:
    period = period_label(reg["date_from"] and date.fromisoformat(reg["date_from"]),
                          reg["date_to"] and date.fromisoformat(reg["date_to"]))
    columns: List[Column] = [
        ("Date", "date", 18, False), ("Invoice No.", "invoice_number", 29, False), ("Flat", "flat", 16, False),
        ("Member", "member", 0, False), ("Billed Rs.", "subtotal", 22, True), ("Tax Rs.", "tax", 18, True),
        ("Total Rs.", "total", 23, True), ("Paid Rs.", "paid", 23, True), ("Due Rs.", "outstanding", 23, True),
        ("Status", "status", 18, False), ("Entered by", "entered_by", 30, False),
    ]
    rows = [{
        "date": _date(r["bill_date"]), "invoice_number": r["invoice_number"], "flat": r["flat"], "member": r["member"],
        "subtotal": _amt(r["subtotal"]), "tax": _amt(r["tax"]), "total": _inr(r["total"]), "paid": _amt(r["paid"]),
        "outstanding": _amt(r["outstanding"]), "status": _STATUS.get(r["status"], r["status"]),
        "entered_by": r["entered_by"] or "System",
    } for r in reg["rows"]]
    t = reg["totals"]
    total = ["", f"{t['count']} invoices", "", "", "", "", _inr(t["total"]), _inr(t["paid"]), _inr(t["outstanding"]), "", ""]
    return _build("Invoice Register", f"Maintenance invoices raised on members · {period}", society,
                  lambda w: [_table(rows, columns, w, total)])


def render_bills_register_pdf(reg: dict, society, *, compress: bool = True) -> bytes:
    period = period_label(reg["date_from"] and date.fromisoformat(reg["date_from"]),
                          reg["date_to"] and date.fromisoformat(reg["date_to"]))
    columns: List[Column] = [
        ("Date", "date", 18, False), ("Bill No.", "invoice_number", 27, False), ("Vendor", "vendor", 0, False),
        ("Expense head", "expense_head", 36, False), ("Amount Rs.", "amount", 22, True), ("GST Rs.", "gst", 18, True),
        ("Total Rs.", "total", 23, True), ("Paid Rs.", "paid", 23, True), ("To pay Rs.", "outstanding", 23, True),
        ("Status", "status", 17, False), ("Entered by", "entered_by", 30, False),
    ]
    rows = [{
        "date": _date(r["invoice_date"]), "invoice_number": r["invoice_number"], "vendor": r["vendor"] or "",
        "expense_head": r["expense_head"] or "", "amount": _amt(r["amount"]), "gst": _amt(r["gst"]),
        "total": _inr(r["total"]), "paid": _amt(r["paid"]), "outstanding": _amt(r["outstanding"]),
        "status": _STATUS.get(r["status"], r["status"]), "entered_by": r["entered_by"] or "",
    } for r in reg["rows"]]
    t = reg["totals"]
    total = ["", f"{t['count']} bills", "", "", "", "", _inr(t["total"]), _inr(t["paid"]), _inr(t["outstanding"]), "", ""]
    return _build("Bills Register", f"Bills received from vendors · {period}", society,
                  lambda w: [_table(rows, columns, w, total)])
