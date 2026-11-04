"""Bank statement PDFs in several different layouts, all made up, to prove the reader does not depend on one bank's
columns. Each layout mimics the way a well-known kind of bank statement is laid out: where the date sits, whether
there is a value-date column, whether debits and credits have a column each or share one with a (Dr)/(Cr) mark, whether
a serial-number column leads, whether the header repeats on every page, how dates and numbers are written.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional

from fpdf import FPDF

from tests.billing.bank_pdf import inr, money

FONT = 8
LINE = 11.2


@dataclass
class Col:
    key: str                       # sno | date | value_date | desc | ref | debit | credit | amount | type | balance | mode
    label: List[str]               # header text, one entry per printed line
    x: float
    w: float
    align: str = "left"


@dataclass
class Layout:
    name: str
    columns: List[Col]
    date_fmt: Callable
    opening: str = "table"         # "table": a dated line in the table | "header": text above it | "none"
    header_every_page: bool = True
    totals: str = "line"           # "line": a Total row under the table | "none"
    closing_row: bool = False
    number: Callable = inr         # how amounts are written
    balance_suffix: str = ""       # "" | " Cr" | "(Cr)"
    amount_suffix: bool = False    # single amount column: "5,000.00(Cr)"
    title: str = "Statement of Account"
    desc_chars: float = 0.0        # wrap width override
    rows_per_page_hint: int = 0


def _d_ddmmmyyyy(d):
    return d.strftime("%d-%b-%Y")


def _d_slash_short(d):
    return d.strftime("%d/%m/%y")


def _d_spaced(d):
    return f"{d.day} {d.strftime('%b')} {d.year}"


def _d_slash_long(d):
    return d.strftime("%d/%m/%Y")


def _d_dash(d):
    return d.strftime("%d-%m-%Y")


def plain(value: Decimal) -> str:
    return f"{abs(value):.2f}"


LAYOUTS = {
    # Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance   (dd/mm/yy, no Cr/Dr)
    "retail_a": Layout(
        "retail_a",
        [Col("date", ["Date"], 24, 40), Col("desc", ["Narration"], 70, 150), Col("ref", ["Chq./Ref.No."], 226, 70),
         Col("value_date", ["Value Dt"], 300, 44), Col("debit", ["Withdrawal Amt."], 348, 70, "right"),
         Col("credit", ["Deposit Amt."], 422, 66, "right"), Col("balance", ["Closing Balance"], 492, 80, "right")],
        _d_slash_short, opening="header", totals="none"),
    # Txn Date | Value Date | Description | Ref No./Cheque No. | Debit | Credit | Balance   ("1 Oct 2026")
    "retail_b": Layout(
        "retail_b",
        [Col("date", ["Txn Date"], 24, 50), Col("value_date", ["Value Date"], 78, 50), Col("desc", ["Description"], 132, 150),
         Col("ref", ["Ref No./Cheque No."], 288, 80), Col("debit", ["Debit"], 372, 60, "right"),
         Col("credit", ["Credit"], 436, 60, "right"), Col("balance", ["Balance"], 500, 72, "right")],
        _d_spaced, opening="table", totals="line"),
    # S No. | Value Date | Transaction Date | Cheque Number | Transaction Remarks | Withdrawal Amount | Deposit Amount | Balance
    "retail_c": Layout(
        "retail_c",
        [Col("sno", ["S No."], 24, 22), Col("value_date", ["Value Date"], 50, 50), Col("date", ["Transaction", "Date"], 104, 52),
         Col("ref", ["Cheque", "Number"], 160, 60), Col("desc", ["Transaction", "Remarks"], 226, 140),
         Col("debit", ["Withdrawal", "Amount (INR)"], 372, 62, "right"), Col("credit", ["Deposit", "Amount (INR)"], 438, 62, "right"),
         Col("balance", ["Balance", "(INR)"], 504, 68, "right")],
        _d_slash_long, opening="none", totals="none", closing_row=True),
    # Date | Narration | Chq/Ref No | Withdrawal(Dr)/Deposit(Cr) | Balance   — one amount column, "(Cr)"/"(Dr)" after each figure
    "single_amount": Layout(
        "single_amount",
        [Col("date", ["Date"], 24, 48), Col("desc", ["Narration"], 76, 170), Col("ref", ["Chq/Ref No"], 250, 70),
         Col("amount", ["Withdrawal(Dr)/", "Deposit(Cr)"], 324, 90, "right"), Col("balance", ["Balance"], 420, 100, "right")],
        _d_dash, opening="table", totals="none", amount_suffix=True, balance_suffix="(Cr)"),
    # SRL NO | Tran Date | CHQNO | PARTICULARS | DR | CR | BAL   — no digit grouping, header printed on the first page only
    "plain_numbers": Layout(
        "plain_numbers",
        [Col("sno", ["SRL NO"], 24, 30), Col("date", ["Tran Date"], 58, 52), Col("ref", ["CHQNO"], 114, 60),
         Col("desc", ["PARTICULARS"], 180, 170), Col("debit", ["DR"], 356, 60, "right"), Col("credit", ["CR"], 420, 60, "right"),
         Col("balance", ["BAL"], 486, 86, "right")],
        _d_dash, opening="table", totals="none", number=plain, header_every_page=False),
    # Date | Description | Reference | Amount | Dr/Cr | Balance   — a separate Dr/Cr column next to one amount column
    "type_column": Layout(
        "type_column",
        [Col("date", ["Date"], 24, 50), Col("desc", ["Description"], 78, 170), Col("ref", ["Reference"], 252, 70),
         Col("amount", ["Amount"], 326, 70, "right"), Col("type", ["Dr/Cr"], 400, 24), Col("balance", ["Balance"], 430, 142, "right")],
        _d_ddmmmyyyy, opening="table", totals="none", balance_suffix=" Cr"),
    # Date | Particulars | Amount | Balance   — one plain amount column, no marks: only the balance tells debit from credit
    "amount_only": Layout(
        "amount_only",
        [Col("date", ["Date"], 24, 50), Col("desc", ["Particulars"], 80, 200), Col("amount", ["Amount"], 290, 80, "right"),
         Col("balance", ["Balance"], 400, 120, "right")],
        _d_slash_long, opening="table", totals="none"),
    # Date | Details | Debit | Credit | Balance   — no reference column at all
    "no_reference": Layout(
        "no_reference",
        [Col("date", ["Date"], 24, 54), Col("desc", ["Details"], 84, 210), Col("debit", ["Debit"], 300, 70, "right"),
         Col("credit", ["Credit"], 376, 70, "right"), Col("balance", ["Balance"], 452, 110, "right")],
        _d_ddmmmyyyy, opening="header", totals="none", balance_suffix=" Cr"),
}


def build_layout_pdf(layout: Layout, rows: List[dict], opening="100000.00", account="000000000123",
                     balance_override: Optional[dict] = None, printed_totals: object = True,
                     bank: str = "Sample Urban Co-op. Bank Ltd", wrap_w: float = 0.0, font: float = FONT,
                     page_date_line: bool = False) -> bytes:
    global FONT
    FONT = font
    pdf = FPDF(unit="pt", format="A4")
    pdf.set_auto_page_break(False)
    cols = {c.key: c for c in layout.columns}
    desc_w = wrap_w or (cols["desc"].w - 4)

    def put(x, y, txt, bold=False, right=None):
        pdf.set_font("Helvetica", style="B" if bold else "", size=FONT)
        if right is not None:
            x = right - pdf.get_string_width(txt)
        pdf.text(x, y, txt)

    def put_col(col: Col, y: float, txt: str, bold=False):
        if col.align == "right":
            put(0, y, txt, bold, right=col.x + col.w)
        else:
            put(col.x, y, txt, bold)

    def wrap(text: str) -> List[str]:
        pdf.set_font("Helvetica", size=FONT)
        out, cur = [], ""
        for token in text.split(" "):
            cand = (cur + " " + token) if cur else token
            if pdf.get_string_width(cand) <= desc_w:
                cur = cand
                continue
            if cur:
                out.append(cur)
                cur = ""
            while pdf.get_string_width(token) > desc_w:
                cut = len(token)
                while pdf.get_string_width(token[:cut]) > desc_w:
                    cut -= 1
                out.append(token[:cut])
                token = token[cut:]
            cur = token
        if cur:
            out.append(cur)
        return out

    def fmt_balance(v: Decimal) -> str:
        suffix = layout.balance_suffix
        if v < 0:
            suffix = suffix.replace("Cr", "Dr") if suffix else ""
        return ("-" if v < 0 and not layout.balance_suffix else "") + layout.number(v) + suffix

    bal = money(opening)
    items = []
    for i, r in enumerate(rows):
        bal = bal + (r["credit"] or 0) - (r["debit"] or 0)
        items.append((i, r, wrap(r["desc"]), (balance_override or {}).get(i, bal)))
    total_d = sum((r["debit"] or 0 for r in rows), Decimal(0))
    total_c = sum((r["credit"] or 0 for r in rows), Decimal(0))
    first_date = datetime.strptime(rows[0]["date"], "%d-%b-%Y")
    last_date = datetime.strptime(rows[-1]["date"], "%d-%b-%Y")

    def header(top: float) -> float:
        n = max(len(c.label) for c in layout.columns)
        for c in layout.columns:
            for k, text in enumerate(c.label):
                offset = (n - len(c.label)) * 0.0
                w = pdf.get_string_width(text)
                x = c.x + (c.w - w) / 2 if c.align == "right" or len(c.label) > 1 else c.x
                put(x, top + k * 6.0 + offset, text, bold=True)
        return top + (n - 1) * 6.0 + 18

    # paginate
    pages: List[list] = [[]]
    used = 0.0
    first_cap, other_cap = 560.0, 700.0
    for it in items:
        h = max(len(it[2]), 1) * LINE + 8
        if used + h > (first_cap if len(pages) == 1 else other_cap) and pages[-1]:
            pages.append([])
            used = 0.0
        pages[-1].append(it)
        used += h

    total_pages = len(pages)
    for n, chunk in enumerate(pages, start=1):
        pdf.add_page()
        if n == 1:
            put(180, 40, bank, bold=True)
            put(24, 62, layout.title, bold=True)
            put(24, 78, f"Account No : {account}")
            put(24, 90, f"Statement period : {layout.date_fmt(first_date)} to {layout.date_fmt(last_date)}")
            if layout.opening == "header":
                put(24, 102, f"Opening Balance : {fmt_balance(money(opening))}")
            top = 130.0
        else:
            put(180, 40, bank, bold=True)
            if page_date_line:
                put(24, 56, "Statement date:")
                put(24 + 60, 56, layout.date_fmt(last_date))
            top = 70.0
        y = top
        if n == 1 or layout.header_every_page:
            y = header(top)
        else:
            y = top + 4
        if n == 1 and layout.opening == "table":
            put_col(cols["date"], y, layout.date_fmt(first_date))
            put_col(cols["desc"], y, "Opening Balance")
            put_col(cols["balance"], y, fmt_balance(money(opening)))
            y += LINE + 8
        for i, r, lines, shown in chunk:
            d = datetime.strptime(r["date"], "%d-%b-%Y")
            if "sno" in cols:
                put_col(cols["sno"], y, str(i + 1))
            put_col(cols["date"], y, layout.date_fmt(d))
            if "value_date" in cols:
                put_col(cols["value_date"], y, layout.date_fmt(d))
            if "ref" in cols:
                put_col(cols["ref"], y, r["ref"])
            for k, text in enumerate(lines):
                put_col(cols["desc"], y + k * LINE, text)
            money_dir = "credit" if r["credit"] else "debit"
            amount = r["credit"] or r["debit"]
            if "amount" in cols:
                txt = layout.number(amount) + (("(Cr)" if money_dir == "credit" else "(Dr)") if layout.amount_suffix else "")
                put_col(cols["amount"], y, txt)
                if "type" in cols:
                    put_col(cols["type"], y, "Cr" if money_dir == "credit" else "Dr")
            else:
                if r["debit"] is not None:
                    put_col(cols["debit"], y, layout.number(r["debit"]))
                if r["credit"] is not None:
                    put_col(cols["credit"], y, layout.number(r["credit"]))
            put_col(cols["balance"], y, fmt_balance(shown))
            y += max(len(lines), 1) * LINE + 8
        if n == total_pages:
            if layout.closing_row:
                put_col(cols["desc"], y, "Closing Balance")
                put_col(cols["balance"], y, fmt_balance(bal))
                y += LINE + 8
            if layout.totals == "line" and printed_totals is not False and "debit" in cols:
                d, c = (total_d, total_c) if printed_totals is True else printed_totals
                y += 6
                put_col(cols["desc"], y, "Total", bold=True)
                put_col(cols["debit"], y, layout.number(money(d)), bold=True)
                put_col(cols["credit"], y, layout.number(money(c)), bold=True)
        put(500, 820, f"Page {n} of {total_pages}")
        put(24, 820, "This is a system generated statement and does not require a signature.")
    return bytes(pdf.output())
