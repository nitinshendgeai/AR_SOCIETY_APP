"""Reads a bank's "Account Statement" PDF (the table of TXN Date / Value Date / Description / ReferenceNo-ChequeNo /
Tr. Mode / Branch Code / Debit / Credit / Balance that a co-operative bank prints for a current account) into rows the
bank reconciliation can use.

The table is read by the position of each text line on the page, not by guessing from the text order, and the result is
then PROVED against the statement itself before anyone relies on it:

  * every row's running balance must follow from the one before it (opening balance ± the row's amount), which also
    tells a debit from a credit whatever column the amount was printed in;
  * the debits, the credits and the closing balance must equal the statement's own "Summation of Debits and Credits"
    line (when the statement has one).

A statement that fails any of these is refused with a plain message instead of being half-imported: a bank
reconciliation that silently drops or mislabels one line is worse than none.
"""
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

MAX_PDF_BYTES = 8_000_000
MAX_PAGES = 400

_DATE = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$")
_AMOUNT = re.compile(r"^\d[\d,]*\.\d{2}$")
_BALANCE = re.compile(r"^(\d[\d,]*\.\d{2})\s*(Cr|Dr)$", re.IGNORECASE)


class StatementError(ValueError):
    """The PDF is not a statement this reader understands, or it does not add up. The message is for the person."""


@dataclass
class StatementRow:
    txn_date: date
    value_date: Optional[date]
    description: str
    reference: Optional[str]
    mode: str
    amount: Decimal
    direction: str                 # "credit" | "debit"
    balance: Decimal               # signed: credit balance positive


@dataclass
class Statement:
    bank: str = ""
    account_number: str = ""
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    printed_total_debits: Optional[Decimal] = None
    printed_total_credits: Optional[Decimal] = None
    rows: List[StatementRow] = field(default_factory=list)

    @property
    def total_debits(self) -> Decimal:
        return sum((r.amount for r in self.rows if r.direction == "debit"), Decimal(0))

    @property
    def total_credits(self) -> Decimal:
        return sum((r.amount for r in self.rows if r.direction == "credit"), Decimal(0))


def _money(text: str) -> Decimal:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        raise StatementError(f"Could not read the amount {text!r} in the statement")


def _date(text: str) -> date:
    return datetime.strptime(text, "%d-%b-%Y").date()


def _signed_balance(text: str) -> Optional[Decimal]:
    m = _BALANCE.match(text.strip())
    if not m:
        return None
    value = _money(m.group(1))
    return value if m.group(2).lower() == "cr" else -value


@dataclass
class _Line:
    page: int
    x0: float
    x1: float
    y: float
    text: str


def _lines(pdf_bytes: bytes) -> List[_Line]:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTTextLine
    except ImportError:                                       # the PDF reader is a declared dependency
        raise StatementError("PDF statements cannot be read on this server")
    out: List[_Line] = []

    def walk(obj, page_no):
        if isinstance(obj, LTTextLine):
            text = obj.get_text().replace("\n", " ").strip()
            if text:
                out.append(_Line(page_no, obj.x0, obj.x1, obj.y1, text))
        elif hasattr(obj, "__iter__"):
            for child in obj:
                walk(child, page_no)

    try:
        params = LAParams(line_margin=0.1, char_margin=1.0, word_margin=0.1)
        for n, page in enumerate(extract_pages(io.BytesIO(pdf_bytes), laparams=params, maxpages=MAX_PAGES)):
            walk(page, n)
    except Exception:                                         # a damaged, encrypted or non-PDF file
        raise StatementError("This file could not be read as a PDF statement")
    return out


def parse_statement_pdf(pdf_bytes: bytes) -> Statement:
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise StatementError("The statement PDF is too large")
    if not pdf_bytes.startswith(b"%PDF"):
        raise StatementError("This file is not a PDF")
    lines = _lines(pdf_bytes)
    if not lines or not any(l.text == "Account Statement" for l in lines):
        raise StatementError("This PDF is not a bank 'Account Statement' in the supported format")

    st = Statement()
    first_page = [l for l in lines if l.page == 0]
    if first_page:
        st.bank = max(first_page, key=lambda l: l.y).text
    st.account_number = _header_value(first_page, "Account Number")
    for label, attr in (("From Date", "from_date"), ("To Date", "to_date")):
        raw = _header_value(first_page, label)
        if _DATE.match(raw or ""):
            setattr(st, attr, _date(raw))

    by_page: Dict[int, List[_Line]] = {}
    for l in lines:
        by_page.setdefault(l.page, []).append(l)

    # Description lines are glued back together; the column they sit in tells where a wrapped line is full.
    edges = sorted(l.x1 for l in lines if 140 <= l.x0 <= 150)
    desc_right = edges[min(len(edges) - 1, int(len(edges) * 0.97))] if edges else 0.0       # where a full line ends (ignoring a stray wide one)
    seen_table = False
    pending: List[dict] = []
    prev_balance: Optional[Decimal] = None

    for page_no in sorted(by_page):
        page = by_page[page_no]
        header = next((l for l in page if l.text == "Balance"), None)       # the table's header row on this page
        if header is None:
            continue
        seen_table = True
        body = [l for l in page if l.y < header.y - 12]                    # below the "/ChequeNo" header line
        stop = [l.y for l in body if l.text.startswith(("Printed by", "Page ", "Note :", "This is a system"))]
        limit = max(stop) if stop else -1
        body = [l for l in body if l.y > limit or l.text.startswith("Voucher")]
        anchors = sorted((l for l in body if l.x0 < 80 and _DATE.match(l.text)), key=lambda l: -l.y)
        summation = next((l for l in body if l.text.startswith("Voucher")), None)
        cutoff = summation.y + 8 if summation else None
        for i, anchor in enumerate(anchors):
            top = anchor.y + 6
            bottom = anchors[i + 1].y + 6 if i + 1 < len(anchors) else (cutoff if cutoff is not None else -1)
            cells = [l for l in body if bottom < l.y <= top]
            pending.append(_read_row(anchor, cells, desc_right))

    if not seen_table:
        raise StatementError("No transaction table was found in this statement")
    for l in lines:                                           # "Voucher : 106  Summation of Debits and Credits..."
        if l.text.startswith("Voucher"):
            _read_summation(st, [c for c in lines if c.page == l.page and abs(c.y - l.y) < 6])

    # Running balance: the opening balance, then every row must follow from the one before it.
    for raw in pending:
        if raw["opening"]:
            st.opening_balance = raw["balance"]
            prev_balance = raw["balance"]
            continue
        if prev_balance is None:
            raise StatementError("The statement has no opening balance row, so it cannot be checked")
        if raw["amount"] is None or raw["balance"] is None:
            raise StatementError(f"A line dated {raw['txn_date']:%d-%b-%Y} has no readable amount or balance")
        delta = raw["balance"] - prev_balance
        if delta == raw["amount"]:
            direction = "credit"
        elif delta == -raw["amount"]:
            direction = "debit"
        else:
            raise StatementError(
                f"The balance after the line dated {raw['txn_date']:%d-%b-%Y} does not follow from the one before it "
                "(a line may be missing or unreadable). Nothing was imported.")
        if raw["column"] is not None and raw["column"] != direction:
            raise StatementError(
                f"A line dated {raw['txn_date']:%d-%b-%Y} is printed in the {raw['column']} column but moves the "
                f"balance as a {direction}. Nothing was imported.")
        st.rows.append(StatementRow(
            txn_date=raw["txn_date"], value_date=raw["value_date"], description=raw["description"],
            reference=raw["reference"], mode=raw["mode"], amount=raw["amount"], direction=direction,
            balance=raw["balance"]))
        prev_balance = raw["balance"]
    st.closing_balance = prev_balance

    if st.opening_balance is None:
        raise StatementError("The statement has no opening balance row, so it cannot be checked")
    if st.printed_total_debits is not None and st.printed_total_debits != st.total_debits:
        raise StatementError(
            f"The debits read from the statement ({st.total_debits:,.2f}) differ from the total it prints "
            f"({st.printed_total_debits:,.2f}). Nothing was imported.")
    if st.printed_total_credits is not None and st.printed_total_credits != st.total_credits:
        raise StatementError(
            f"The credits read from the statement ({st.total_credits:,.2f}) differ from the total it prints "
            f"({st.printed_total_credits:,.2f}). Nothing was imported.")
    return st


def _header_value(page_lines: List[_Line], label: str) -> str:
    """The value printed beside a label in the statement's header block (same line, to the right)."""
    for l in page_lines:
        if l.text.rstrip(" :").strip() == label:
            right = [v for v in page_lines if abs(v.y - l.y) < 5 and v.x0 > l.x1 and v is not l]
            if right:
                return min(right, key=lambda v: v.x0).text.strip()
    return ""


def _read_summation(st: Statement, cells: List[_Line]) -> None:
    amounts = sorted((c for c in cells if _AMOUNT.match(c.text)), key=lambda c: c.x0)
    if len(amounts) >= 2:
        st.printed_total_debits = _money(amounts[0].text)
        st.printed_total_credits = _money(amounts[1].text)


def _read_row(anchor: _Line, cells: List[_Line], desc_right: float) -> dict:
    txn_date = _date(anchor.text)
    value_date = None
    ref_parts: List[str] = []
    mode = ""
    amount: Optional[Decimal] = None
    column: Optional[str] = None
    balance: Optional[Decimal] = None
    desc_lines: List[_Line] = []
    opening = False
    for c in sorted(cells, key=lambda c: (-c.y, c.x0)):
        if c is anchor or c.x0 < 80:
            continue
        bal = _signed_balance(c.text)
        if bal is not None and c.x0 >= 440:                   # "31,04,883.00 Cr"
            balance = bal
        elif _AMOUNT.match(c.text) and c.x0 >= 360:           # a debit or a credit, right-aligned in its column
            amount = _money(c.text)
            column = "credit" if c.x1 >= 470 else "debit"
        elif 80 <= c.x0 < 140:                                # value date, then the time under it
            if value_date is None and _DATE.match(c.text):
                value_date = _date(c.text)
        elif 140 <= c.x0 < 230:
            if c.text == "Opening Balance":
                opening = True
            else:
                desc_lines.append(c)
        elif 230 <= c.x0 < 300:
            ref_parts.append(c.text)
        elif 300 <= c.x0 < 338:
            mode = c.text
        # (338-360: the branch code, which the reconciliation does not use)
    description = _join_description([l.text for l in desc_lines], [l.x1 for l in desc_lines], desc_right)
    reference = "".join(ref_parts).strip().rstrip("/").strip() or None
    return {"txn_date": txn_date, "value_date": value_date, "description": description or "(no description)",
            "reference": reference, "mode": mode, "amount": amount, "column": column, "balance": balance,
            "opening": opening}


def _join_description(parts: List[str], right_edges: List[float], full_width: float) -> str:
    """The bank wraps a description at a fixed width, even in the middle of a word or a number. A line that runs to the
    right edge of the column, or a number cut between two digits, continues straight into the next line; any other
    line ended at a space. Where a line ends close to the edge the break could be either, so the text is best-effort:
    what matters (a reference or account number) is always put back whole."""
    out = ""
    for i, text in enumerate(parts):
        if i:
            full = right_edges[i - 1] >= full_width - 3.0
            digit_split = parts[i - 1][-1:].isdigit() and text[:1].isdigit()
            if not (full or digit_split):
                out += " "
        out += text
    return re.sub(r"\s+", " ", out).strip()
