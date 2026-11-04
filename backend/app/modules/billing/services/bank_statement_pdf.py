"""Reads a bank statement PDF into rows the bank reconciliation can use, whatever bank printed it.

Banks do not share a layout, so nothing here depends on where a column sits on the page. The table is found the way a
person finds it:

  1. every page's text is cut into cells (pieces of text separated by a gap) and lines, using the position of each
     character;
  2. the table's header row is found by its labels (Date / Txn Date / Value Date, Description / Narration / Particulars,
     Chq / Ref No, Debit / Withdrawal / Dr, Credit / Deposit / Cr, Balance, or one Amount column ...), also when a label
     is wrapped over two or three lines;
  3. each cell below it is put in the column whose header it sits under; a row starts at a date and runs to the next
     date, so a description wrapped over several lines stays with its row.

Reading is then PROVED against the statement itself before anyone relies on it. A reading that cannot be proved is
refused with a plain message, never half-imported:

  * every row's running balance must follow from the one before it (opening balance +/- the row's amount), which also
    tells a debit from a credit whatever column or sign the amount was printed with, and a debit/credit column or a
    Dr/Cr mark that disagrees with the balance is refused;
  * the debits, the credits and the closing balance must equal the statement's own totals, where it prints them;
  * a statement with neither a running balance nor printed totals cannot be checked, so it is refused.

If the first reading fails the proof, the reader tries a few other ways of cutting the same page before giving up.
Scanned (picture-only) and password-protected PDFs are refused with a message saying so.
"""
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

MAX_PDF_BYTES = 8_000_000
MAX_PAGES = 400


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
    balance: Optional[Decimal]     # signed: credit balance positive


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
    balances_checked: bool = False
    rows: List[StatementRow] = field(default_factory=list)

    @property
    def total_debits(self) -> Decimal:
        return sum((r.amount for r in self.rows if r.direction == "debit"), Decimal(0))

    @property
    def total_credits(self) -> Decimal:
        return sum((r.amount for r in self.rows if r.direction == "credit"), Decimal(0))

    @property
    def account_is_masked(self) -> bool:
        return bool(re.search(r"[xX*]", self.account_number or ""))


# ── numbers and dates ────────────────────────────────────────────────────────

_NUM = re.compile(
    r"^(?:rs\.?|inr|₹)?\s*(\()?\s*(-|\+)?\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*\.\d{1,2})\s*(\))?\s*(?:\(?\s*(cr|dr)\s*\)?\.?)?$",
    re.IGNORECASE)
_MARK = re.compile(r"^\(?\s*(cr|dr)\s*\)?\.?$", re.IGNORECASE)
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE_PATTERNS = [
    re.compile(r"^(\d{4})-(\d{2})-(\d{2})\b"),                                          # 2026-10-01
    re.compile(r"^(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{2}|\d{4})(?!\d)"),                  # 01-10-2026, 01/10/26
    re.compile(r"^(\d{1,2})[-/. ]*([A-Za-z]{3,9})[-/. ,]*(\d{2}|\d{4})(?!\d)"),          # 01-Oct-2026, 1 Oct 2026
]


@dataclass
class _Amount:
    value: Decimal
    negative: bool = False
    mark: Optional[str] = None            # "cr" | "dr" when the figure carries one


def _amount(text: str) -> Optional[_Amount]:
    m = _NUM.match(text.strip())
    if not m:
        return None
    try:
        value = Decimal(m.group(3).replace(",", ""))
    except InvalidOperation:
        return None
    return _Amount(value, negative=bool(m.group(1) or m.group(2) == "-"), mark=(m.group(5) or "").lower() or None)


def _date_at_start(text: str) -> Optional[date]:
    text = text.strip()
    for n, pattern in enumerate(_DATE_PATTERNS):
        m = pattern.match(text)
        if not m:
            continue
        try:
            if n == 0:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            a, b, c = m.group(1), m.group(2), m.group(3)
            year = int(c) + (2000 if len(c) == 2 else 0)
            if n == 1:
                return date(year, int(b), int(a))                                      # day first, as banks here print
            month = _MONTHS.get(b[:3].lower())
            return date(year, month, int(a)) if month else None
        except ValueError:
            return None
    return None


# ── reading the page ─────────────────────────────────────────────────────────

@dataclass
class _Cell:
    page: int
    x0: float
    x1: float
    y: float                               # baseline, PDF coordinates (up)
    size: float
    text: str

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2


def _page_lines(pdf_bytes: bytes) -> Tuple[List[List[List[_Cell]]], List[float]]:
    """[page][line][cell], lines top to bottom, cells left to right; and each page's height."""
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTChar
        from pdfminer.pdfparser import PDFSyntaxError
        from pdfminer.pdfdocument import PDFPasswordIncorrect
    except ImportError:                                       # the PDF reader is a declared dependency
        raise StatementError("PDF statements cannot be read on this server")

    def chars_of(obj, out):
        if isinstance(obj, LTChar):
            if obj.get_text().strip():
                out.append(obj)
        elif hasattr(obj, "__iter__"):
            for child in obj:
                chars_of(child, out)

    pages: List[List[List[_Cell]]] = []
    heights: List[float] = []
    try:
        for n, page in enumerate(extract_pages(io.BytesIO(pdf_bytes), laparams=LAParams(boxes_flow=None, detect_vertical=False), maxpages=MAX_PAGES)):
            chars: list = []
            chars_of(page, chars)
            pages.append(_cut_lines(n, chars))
            heights.append(float(page.height))
    except PDFPasswordIncorrect:
        raise StatementError("This PDF is protected with a password. Download an unprotected copy from net banking.")
    except StatementError:
        raise
    except (PDFSyntaxError, Exception):                       # a damaged or non-PDF file
        raise StatementError("This file could not be read as a PDF statement")
    if not any(lines for lines in pages):
        raise StatementError(
            "This PDF has no readable text (it looks like a scan or a photo). Download the statement as a text PDF "
            "from net banking, or use the CSV import.")
    return pages, heights


_ANY_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}[-/. ]\d{1,2}[-/. ]\d{2,4}(?!\d)|\d{1,2}[-/. ]*[A-Za-z]{3,9}[-/. ,]*\d{2,4}(?!\d)")


def _split_double_date(cell: "_Cell") -> List["_Cell"]:
    found = list(_ANY_DATE.finditer(cell.text))
    if len(found) != 2 or cell.text.replace(" ", "") != "".join(m.group(0).replace(" ", "") for m in found):
        return [cell]
    if not all(_date_at_start(m.group(0)) for m in found):
        return [cell]
    cut = found[1].start()
    total = max(len(cell.text), 1)
    mid = cell.x0 + (cell.x1 - cell.x0) * cut / total
    return [_Cell(cell.page, cell.x0, mid - 0.5, cell.y, cell.size, cell.text[:cut].strip()),
            _Cell(cell.page, mid, cell.x1, cell.y, cell.size, cell.text[cut:].strip())]


def _cut_lines(page_no: int, chars: list) -> List[List[_Cell]]:
    def baseline(c) -> float:
        try:
            return float(c.matrix[5])
        except Exception:                                      # noqa: BLE001
            return float(c.y0)

    rows: List[list] = []
    for c in sorted(chars, key=lambda c: (-baseline(c), c.x0)):
        if rows and abs(baseline(rows[-1][0]) - baseline(c)) <= max(1.5, 0.45 * float(c.size)):
            rows[-1].append(c)
        else:
            rows.append([c])
    lines: List[List[_Cell]] = []
    for row in rows:
        row.sort(key=lambda c: c.x0)
        cells: List[List] = [[row[0]]]
        for prev, c in zip(row, row[1:]):
            gap = c.x0 - prev.x1
            if gap > max(2.8, 0.62 * float(c.size)):
                cells.append([c])
            else:
                cells[-1].append(c)
        line = []
        for group in cells:
            text = group[0].get_text()
            for prev, c in zip(group, group[1:]):
                text += (" " if c.x0 - prev.x1 > 0.14 * float(c.size) else "") + c.get_text()
            size = max(float(c.size) for c in group)
            line.extend(_split_double_date(
                _Cell(page_no, group[0].x0, group[-1].x1, sum(baseline(c) for c in group) / len(group), size, text)))
        lines.append(line)
    return lines


# ── the table's header ───────────────────────────────────────────────────────

_NUMERIC_KINDS = ("debit", "credit", "amount", "balance")
_TOTAL_LINE = re.compile(r"total|summation|sum of|grand", re.IGNORECASE)


def _kind_of(label: str) -> str:
    t = re.sub(r"[^a-z/ ]", " ", label.lower())
    t = re.sub(r"\s+", " ", t).strip()
    if re.search(r"\b(dr\s*/\s*cr|cr\s*/\s*dr)\b", t) or t in ("type", "cr dr", "dr cr"):
        return "type"
    if "balance" in t or t in ("bal", "closing bal"):
        return "balance"
    if ("withdraw" in t and "deposit" in t) or ("debit" in t and "credit" in t):
        return "amount"
    if "withdraw" in t or "debit" in t or t in ("dr", "dr amount", "paid out", "payments"):
        return "debit"
    if "deposit" in t or "credit" in t or t in ("cr", "cr amount", "paid in", "receipts"):
        return "credit"
    if "amount" in t or t in ("amt", "amt."):
        return "amount"
    if "value" in t and re.search(r"\b(date|dt)\b", t):
        return "value_date"
    if re.search(r"\b(date|dt)\b", t) or t in ("date", "dt"):
        return "date"
    if re.search(r"descri|narrat|particular|detail|remark|transaction$", t):
        return "desc"
    if re.search(r"\b(chq|cheque|check|ref|reference|instrument|utr)\b|chq|cheque|reference", t):
        return "ref"
    if re.match(r"^(s|sr|srl|sl)\s*/?\s*(no|number)?$", t) or "serial" in t:
        return "sno"
    return "other"


@dataclass
class _Header:
    kind: str
    xc: float
    x0: float
    x1: float


_LEXICON = {
    "debit": {"withdrawal", "withdrawals", "debit", "debits", "dr"},
    "credit": {"deposit", "deposits", "credit", "credits", "cr"},
    "balance": {"balance", "bal"},
    "desc": {"narration", "description", "particulars", "details", "remarks", "narrative"},
    "ref": {"chq", "cheque", "ref", "reference", "instrument", "utr"},
    "date": {"date", "dt"},
}
_MODIFIERS = {"txn", "tran", "transaction", "value", "posting", "booking", "entry"}


def _word_kind(word: str) -> Optional[str]:
    w = re.sub(r"[^a-z]", "", word.lower())
    for kind, words in _LEXICON.items():
        if w in words:
            return kind
    return None


def _split_header_cell(cell: _Cell) -> List[_Cell]:
    """Two labels printed so close that they read as one cell ("Ref No./Cheque No. Withdrawal Amt.") are cut between the
    words that start a different kind of column. One label that names two things by design ("Debit/Credit",
    "Withdrawal(Dr)/Deposit(Cr)") is left whole."""
    words = cell.text.split()
    if len(words) < 2 or re.search(r"\)\s*/|/\s*\(?(dr|cr|deposit|credit|withdrawal|debit)", cell.text, re.IGNORECASE):
        return [cell]
    segments: List[List[str]] = [[]]
    seg_kind: Optional[str] = None
    for w in words:
        k = _word_kind(w)
        if k and seg_kind and k != seg_kind and not (seg_kind == "date" and k == "date"):
            trailing = []
            while segments[-1] and re.sub(r"[^a-z]", "", segments[-1][-1].lower()) in _MODIFIERS:
                trailing.insert(0, segments[-1].pop())
            segments.append(trailing)
            seg_kind = k
        elif k and not seg_kind:
            seg_kind = k
        segments[-1].append(w)
    segments = [sg for sg in segments if sg]
    # "Transaction Value Dt" over "Date": the lone qualifier belongs to the label printed below it
    if (len(segments) == 1 and len(words) >= 3
            and re.sub(r"[^a-z]", "", words[0].lower()) in ("transaction", "txn", "trans", "posting", "booking")
            and _word_kind(words[0]) is None and any(_word_kind(w) for w in words[1:])):
        segments = [words[:1], words[1:]]
    if len(segments) < 2:
        return [cell]
    total = sum(len(" ".join(sg)) for sg in segments)
    out, x = [], cell.x0
    for sg in segments:
        width = (cell.x1 - cell.x0) * len(" ".join(sg)) / total
        out.append(_Cell(cell.page, x, x + width, cell.y, cell.size, " ".join(sg)))
        x += width
    return out


def _has_data(line: List[_Cell]) -> bool:
    return any(_date_at_start(c.text) or _amount(c.text) or _ANY_DATE.search(c.text) for c in line)


def _headers_of(band: List[List[_Cell]]) -> List[_Header]:
    # stack the labels of one column over the lines of the band (two cells of one line are never one column)
    groups: List[List[Tuple[int, _Cell]]] = []
    for li, ln in enumerate(band):
        for cell in [part for c in ln for part in _split_header_cell(c)]:
            for g in groups:
                if all(k != li for k, _ in g) and abs(sum(m.xc for _, m in g) / len(g) - cell.xc) <= 16:
                    g.append((li, cell))
                    break
            else:
                groups.append([(li, cell)])
    headers = []
    for g in groups:
        cells_ = [c for _, c in g]
        label = " ".join(c.text for c in sorted(cells_, key=lambda c: -c.y))
        headers.append(_Header(_kind_of(label), sum(c.xc for c in cells_) / len(cells_),
                               min(c.x0 for c in cells_), max(c.x1 for c in cells_)))
    return headers


def _find_header(lines: List[List[_Cell]]) -> Optional[Tuple[List[_Header], int]]:
    """The table's header on the page: ([_Header], index of the first line below it). Every band of one to three
    lines is tried; the one whose labels name the most different columns, with the fewest repeats, wins (a "Statement
    date" line above the header must not steal a label from it)."""
    best = None
    for i, line in enumerate(lines[:80]):
        if _has_data(line):
            continue
        band = [line]
        while True:
            headers = _headers_of(band)
            kinds = [h.kind for h in headers if h.kind != "other"]
            distinct = set(kinds)
            if ({"date", "value_date"} & distinct) and (distinct & set(_NUMERIC_KINDS)) and len(distinct) >= 3:
                score = (len(distinct) * 10 - (len(kinds) - len(distinct)) * 6, len(band), -i)
                if best is None or score > best[0]:
                    best = (score, headers, i + len(band))
            j = i + len(band)
            size = max(c.size for c in line)
            if len(band) >= 3 or j >= len(lines) or _has_data(lines[j]) or band[-1][0].y - lines[j][0].y > 2.2 * size:
                break
            band.append(lines[j])
    return (best[1], best[2]) if best else None


# ── rows ─────────────────────────────────────────────────────────────────────

_OPENING = re.compile(r"opening\s+bal|balance\s+(b/?f|brought\s+forward)|\bb/?f\b|brought\s+forward", re.IGNORECASE)
_CLOSING = re.compile(r"closing\s+bal|balance\s+(c/?f|carried\s+forward)|carried\s+forward", re.IGNORECASE)
_FIGURE = re.compile(r"(\(?-?\s*\d[\d,]*\.\d{2}\)?)\s*\(?\s*(cr|dr)?\s*\)?", re.IGNORECASE)


def _last_figure(text: str) -> Optional["_Amount"]:
    """The last money figure in a line of text, with its Dr/Cr mark or sign ("Opening Balance : 1,00,000.00 Cr")."""
    found = None
    for m in _FIGURE.finditer(text):
        a = _amount(m.group(1) + (" " + m.group(2) if m.group(2) else ""))
        if a is not None:
            found = a
    return found


_FOOTER = re.compile(r"page\s+\d+\s+(of|/)\s+\d+|printed\s+by|system[- ]generated|end\s+of\s+statement|"
                     r"^\s*note\s*:|computer[- ]generated|registered\s+office|toll\s*free", re.IGNORECASE)


@dataclass
class _RawRow:
    txn_date: date
    value_date: Optional[date]
    parts: List[Tuple[str, float]]           # description lines and their right edges
    ref_parts: List[str]
    mode: str
    debit: Optional[_Amount]
    credit: Optional[_Amount]
    amount: Optional[_Amount]
    balance: Optional[_Amount]
    type_mark: Optional[str]
    text: str


def _distance(cell: _Cell, h: _Header) -> float:
    return min(abs(cell.xc - h.xc), abs(cell.x0 - h.x0), abs(cell.x1 - h.x1))


def _nearest(cell: _Cell, headers: List[_Header], kinds=None) -> Optional[_Header]:
    pool = [h for h in headers if kinds is None or h.kind in kinds]
    return min(pool, key=lambda h: _distance(cell, h)) if pool else None


def _blocks(cells: List[_Cell]) -> List[Tuple[float, float]]:
    """The columns the data itself forms: stretches of the page covered by text, separated by white gaps."""
    out: List[List[float]] = []
    for x0, x1 in sorted((c.x0, c.x1) for c in cells):
        if out and x0 <= out[-1][1] + 1.0:
            out[-1][1] = max(out[-1][1], x1)
        else:
            out.append([x0, x1])
    return [(a, b) for a, b in out]


def _read_page_rows(lines: List[List[_Cell]], start: int, headers: List[_Header], top_factor: float,
                    mode: str) -> Tuple[List[_RawRow], List[List[_Cell]]]:
    """The transaction rows on a page, and the lines left over (balances, totals, page furniture)."""
    body = [ln for ln in lines[start:] if ln]
    date_headers = [h for h in headers if h.kind == "date"] or [h for h in headers if h.kind == "value_date"]
    any_date_headers = [h for h in headers if h.kind in ("date", "value_date")]
    num_headers = [h for h in headers if h.kind in _NUMERIC_KINDS]

    # a row starts at a date that sits under the date column
    anchors: List[Tuple[int, _Cell]] = []
    for li, ln in enumerate(body):
        for c in ln:
            if _date_at_start(c.text) and not _amount(c.text):
                h = min(any_date_headers, key=lambda h: _distance(c, h))
                if h in date_headers and _distance(c, h) <= 30:
                    anchors.append((li, c))
                    break

    def band_of(n: int) -> Tuple[float, float]:
        anchor = anchors[n][1]
        top = anchor.y + top_factor * anchor.size
        bottom = (anchors[n + 1][1].y + top_factor * anchor.size) if n + 1 < len(anchors) else float("-inf")
        return top, bottom

    # the cells of each row; the last row of a page runs on into the page's footer, so it stops where the lines stop
    # being close, or at a footer or a totals / closing-balance line
    pitch = _line_pitch(body)
    row_cells: List[List[Tuple[_Cell, int]]] = []
    for n, (li, anchor) in enumerate(anchors):
        top, bottom = band_of(n)
        cells = [(c, lj) for lj, ln in enumerate(body) for c in ln if bottom < c.y <= top or c is anchor]
        cells.sort(key=lambda p: (p[1], p[0].x0))                       # line by line, left to right
        if n + 1 == len(anchors):
            kept: List[Tuple[_Cell, int]] = []
            prev_y = anchor.y
            for lj in sorted({lj for _c, lj in cells}):
                line = [(c, k) for c, k in cells if k == lj]
                if lj != li:
                    y = max(c.y for c, _k in line)
                    text = " ".join(c.text for c, _k in line)
                    if (prev_y - y > 1.8 * pitch or _FOOTER.search(text) or _TOTAL_LINE.search(text)
                            or _CLOSING.search(text)):
                        break
                    prev_y = y
                kept.extend(line)
            cells = kept
        row_cells.append(cells)
    # the page's columns, from the cells of the rows themselves (never from a footer that spans the page)
    band_cells: List[_Cell] = [c for cells in row_cells for c, _lj in cells]
    blocks = _blocks(band_cells) if mode == "blocks" else []
    votes: Dict[int, Dict[int, int]] = {}
    for c in band_cells:
        if _amount(c.text) and not _date_at_start(c.text) and num_headers:
            h = _nearest(c, num_headers)
            votes.setdefault(round(c.x1 / 3), {}).setdefault(id(h), 0)
            votes[round(c.x1 / 3)][id(h)] += 1
    by_id = {id(h): h for h in num_headers}

    def by_block(cell: _Cell, pool: List[_Header]) -> Optional[_Header]:
        for x0, x1 in blocks:
            if x0 - 0.5 <= cell.xc <= x1 + 0.5:
                over = [(min(x1, h.x1) - max(x0, h.x0), h) for h in pool]
                over = [(o, h) for o, h in over if o > 0]
                if len(over) == 1:
                    return over[0][1]
                if over:
                    return min((h for _o, h in over), key=lambda h: _distance(cell, h))
                break
        return _nearest(cell, pool)

    def column_of(cell: _Cell) -> Optional[_Header]:
        if _amount(cell.text) and not _date_at_start(cell.text) and num_headers:
            slot = votes.get(round(cell.x1 / 3))
            if mode == "blocks":
                return by_block(cell, num_headers)
            if slot:
                return by_id[max(slot, key=lambda k: slot[k])]
            return _nearest(cell, num_headers)
        if _MARK.match(cell.text.strip()):
            pool = [h for h in headers if h.kind == "type"] or num_headers
            return by_block(cell, pool) if mode == "blocks" else _nearest(cell, pool)
        pool = [h for h in headers if h.kind not in _NUMERIC_KINDS]
        return by_block(cell, pool) if mode == "blocks" else _nearest(cell, pool)

    rows: List[_RawRow] = []
    used: set = set()
    for (li, anchor), cells in zip(anchors, row_cells):
        assigned = []
        for c, lj in cells:
            h = column_of(c)
            if h is not None:
                assigned.append((c, h))
                used.add((lj, id(c)))
        rows.append(_build_row(anchor, assigned, headers))
    leftover = [[c for c in ln if (lj, id(c)) not in used] for lj, ln in enumerate(body)]
    return [r for r in rows if r is not None], [ln for ln in leftover if ln]


def _line_pitch(body: List[List[_Cell]]) -> float:
    ys = [ln[0].y for ln in body]
    gaps = sorted(a - b for a, b in zip(ys, ys[1:]) if 0 < a - b < 40)
    return gaps[len(gaps) // 2] if gaps else 11.0


def _build_row(anchor: _Cell, cells: List[Tuple[_Cell, _Header]], headers: List[_Header]) -> Optional[_RawRow]:
    txn = _date_at_start(anchor.text)
    value_date = None
    parts: List[Tuple[str, float]] = []
    refs: List[str] = []
    mode = ""
    amounts: Dict[str, _Amount] = {}
    type_mark = None
    marks: List[Tuple[_Cell, str]] = []
    texts: List[str] = []
    for c, h in cells:
        texts.append(c.text)
        if c is anchor:
            continue
        if h.kind in _NUMERIC_KINDS:
            a = _amount(c.text)
            if a is not None:
                if h.kind not in amounts or amounts[h.kind].value == 0:
                    amounts[h.kind] = a
                continue
        if _MARK.match(c.text.strip()):
            marks.append((c, _MARK.match(c.text.strip()).group(1).lower()))
            continue
        if h.kind == "value_date" or (h.kind == "date" and c is not anchor):
            d = _date_at_start(c.text)
            if d and value_date is None:
                value_date = d
            continue
        if h.kind == "desc":
            parts.append((c.text, c.x1))
        elif h.kind == "ref":
            refs.append(c.text)
        elif h.kind == "other":
            if not mode and not _date_at_start(c.text):
                mode = c.text
        elif h.kind == "type":
            type_mark = c.text.strip().lower()[:2]
    # a lone Dr/Cr mark belongs to the figure printed just left of it
    for mc, mark in marks:
        left = [(c, k) for c, h in cells for k in [h.kind] if k in _NUMERIC_KINDS and c.x1 <= mc.x0 + 1 and abs(c.y - mc.y) < 3]
        if left:
            c, k = max(left, key=lambda p: p[0].x1)
            if k in amounts and amounts[k].mark is None:
                amounts[k].mark = mark
        elif type_mark is None:
            type_mark = mark
    return _RawRow(txn_date=txn, value_date=value_date, parts=parts, ref_parts=refs, mode=mode,
                   debit=amounts.get("debit"), credit=amounts.get("credit"), amount=amounts.get("amount"),
                   balance=amounts.get("balance"), type_mark=type_mark, text=" ".join(texts))


# ── proving the reading ──────────────────────────────────────────────────────

def _signed_balance(a: Optional[_Amount]) -> Optional[Decimal]:
    if a is None:
        return None
    negative = a.negative or a.mark == "dr"
    return -a.value if negative else a.value


def _join_description(parts: List[Tuple[str, float]], full_width: float) -> str:
    """The bank wraps a description at a fixed width, even in the middle of a word or a number. A line that runs to the
    right edge of the column, or a number cut between two digits, continues straight into the next line; any other
    line ended at a space. Where a line ends close to the edge the break could be either, so the text is best-effort:
    what matters (a reference or account number) is always put back whole."""
    out = ""
    for i, (text, right) in enumerate(parts):
        if i:
            prev_text, prev_right = parts[i - 1]
            full = prev_right >= full_width - 3.0
            digit_split = prev_text[-1:].isdigit() and text[:1].isdigit()
            if not (full or digit_split):
                out += " "
        out += text
    return re.sub(r"\s+", " ", out).strip()


def _prove(raw_rows: List[_RawRow], opening: Optional[Decimal], full_width: float) -> Tuple[List[StatementRow], Decimal, bool]:
    """Turns raw rows into statement rows, or raises StatementError when the reading cannot be proved."""
    out: List[StatementRow] = []
    prev = opening
    chain = True
    for raw in raw_rows:
        # the amount and the direction the page itself prints
        printed: Optional[Decimal] = None
        column: Optional[str] = None
        if raw.debit is not None and raw.debit.value > 0 and not (raw.credit is not None and raw.credit.value > 0):
            printed, column = raw.debit.value, "debit"
        elif raw.credit is not None and raw.credit.value > 0 and not (raw.debit is not None and raw.debit.value > 0):
            printed, column = raw.credit.value, "credit"
        elif raw.amount is not None and raw.amount.value > 0:
            printed = raw.amount.value
            mark = raw.amount.mark or raw.type_mark
            if mark == "dr" or raw.amount.negative:
                column = "debit"
            elif mark == "cr":
                column = "credit"
        elif (raw.debit is not None and raw.debit.value > 0) and (raw.credit is not None and raw.credit.value > 0):
            raise StatementError(f"A line dated {raw.txn_date:%d-%b-%Y} shows both a debit and a credit. Nothing was imported.")
        else:
            continue                                                       # a dated line with no money in it
        balance = _signed_balance(raw.balance)
        if prev is None:                                                   # no opening balance printed: work it back
            if balance is None or column is None:
                raise StatementError("The statement's opening balance could not be found, so it cannot be checked. "
                                     "Nothing was imported.")
            prev = balance - printed if column == "credit" else balance + printed
        if balance is None:
            chain = False
            if column is None:
                raise StatementError(f"The line dated {raw.txn_date:%d-%b-%Y} has no balance and no debit or credit mark, "
                                     "so it cannot be checked. Nothing was imported.")
            direction = column
            new_balance = None
        else:
            delta = balance - prev
            if delta == printed:
                direction = "credit"
            elif delta == -printed:
                direction = "debit"
            else:
                raise StatementError(
                    f"The balance after the line dated {raw.txn_date:%d-%b-%Y} does not follow from the one before it "
                    "(a line may be missing or unreadable). Nothing was imported.")
            if column is not None and column != direction:
                raise StatementError(
                    f"A line dated {raw.txn_date:%d-%b-%Y} is printed as a {column} but moves the balance as a "
                    f"{direction}. Nothing was imported.")
            new_balance = balance
        ref = "".join(raw.ref_parts).strip().rstrip("/").strip() or None
        out.append(StatementRow(
            txn_date=raw.txn_date, value_date=raw.value_date,
            description=_join_description(raw.parts, full_width) or "(no description)", reference=ref,
            mode=raw.mode, amount=printed, direction=direction, balance=new_balance))
        prev = new_balance if new_balance is not None else (prev + printed if direction == "credit" else prev - printed)
    return out, (prev if prev is not None else Decimal(0)), chain


def _find_totals(trailer: List[str], debits: Decimal, credits: Decimal) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """The statement's own totals line (after the last transaction), as (printed debits, printed credits)."""
    for text in reversed(trailer):                                              # the last totals line is the statement's
        if not _TOTAL_LINE.search(text):
            continue
        figures = [a.value for tok in re.findall(r"\d[\d,]*\.\d{2}", text) for a in [_amount(tok)] if a]
        if len(figures) < 2:
            continue
        if debits in figures and credits in figures:
            return debits, credits
        return figures[0], figures[1]                                       # the first two figures are debits, credits
    return None, None


def _statement_meta(lines_by_page: List[List[List[_Cell]]], st: Statement) -> None:
    head = [" ".join(c.text for c in ln) for pg in lines_by_page[:2] for ln in pg[:60]]
    for text in head:
        if not st.bank and re.search(r"\bbank\b|\bco-?op", text, re.IGNORECASE) and len(text) < 90:
            st.bank = text.strip()
        if not st.account_number:
            m = re.search(r"(?:a/?c\.?|account)\s*(?:no\.?|number|num\.?)?\s*[:\-]?\s*([0-9xX*][0-9xX* \-]{5,})", text, re.IGNORECASE)
            if m:
                st.account_number = re.sub(r"[\s\-]+$", "", m.group(1)).replace(" ", "")
        if st.from_date is None and re.search(r"from|period|statement\s+(date|for)", text, re.IGNORECASE):
            found = []
            for m in re.finditer(r"\d{1,2}[-/. ][A-Za-z0-9]{1,9}[-/. ,]*\d{2,4}|\d{4}-\d{2}-\d{2}", text):
                d = _date_at_start(m.group(0))
                if d:
                    found.append(d)
            if len(found) >= 2:
                st.from_date, st.to_date = found[0], found[1]


def parse_statement_pdf(pdf_bytes: bytes) -> Statement:
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise StatementError("The statement PDF is too large")
    if not pdf_bytes.startswith(b"%PDF"):
        raise StatementError("This file is not a PDF")
    pages, _heights = _page_lines(pdf_bytes)

    # the table's header on each page (a page without its own uses the last one seen)
    headers_for: List[Tuple[List[_Header], int]] = []
    last: Optional[List[_Header]] = None
    found_any = False
    for lines in pages:
        h = _find_header(lines)
        if h is not None:
            last, found_any = h[0], True
            headers_for.append((h[0], h[1]))
        elif last is not None:
            headers_for.append((last, 0))
        else:
            headers_for.append(([], -1))
    if not found_any:
        raise StatementError(
            "No transaction table (a Date column with Debit/Credit or Amount and Balance columns) was found in this "
            "PDF, so it is not a bank statement this reader understands. Use the CSV import instead.")

    # a few ways of cutting the same page; the first one that proves itself is used
    first_error: Optional[StatementError] = None
    for top_factor, mode in ((0.6, "blocks"), (1.1, "blocks"), (0.6, "nearest"), (1.6, "nearest")):
        try:
            return _attempt(pages, headers_for, top_factor, mode)
        except StatementError as exc:
            first_error = first_error or exc
    raise first_error  # type: ignore[misc]


def _attempt(pages, headers_for, top_factor: float, mode: str) -> Statement:
    st = Statement()
    raw_rows: List[_RawRow] = []
    trailer: List[str] = []
    opening: Optional[Decimal] = None
    closing_printed: Optional[Decimal] = None
    desc_edges: List[float] = []
    for n, lines in enumerate(pages):
        headers, start = headers_for[n]
        if start < 0 or not headers:
            continue
        rows, leftover = _read_page_rows(lines, start, headers, top_factor, mode)
        for ln in leftover:
            text = " ".join(c.text for c in ln)
            figure = _last_figure(text)
            if _OPENING.search(text) and figure and opening is None:
                opening = _signed_balance(figure)
            elif _CLOSING.search(text) and figure:
                closing_printed = _signed_balance(figure)
            else:
                trailer.append(text)
        kept = []
        for r in rows:
            if _OPENING.search(r.text) and r.debit is None and r.credit is None and r.amount is None and r.balance is not None:
                opening = _signed_balance(r.balance) if opening is None else opening
                continue
            if _CLOSING.search(r.text) and r.debit is None and r.credit is None and r.amount is None and r.balance is not None:
                closing_printed = _signed_balance(r.balance)
                continue
            kept.append(r)
        raw_rows.extend(kept)
        desc_edges.extend(right for r in kept for _t, right in r.parts)
    if opening is None:
        for lines in pages:
            for ln in lines:
                text = " ".join(c.text for c in ln)
                figure = _last_figure(text)
                if _OPENING.search(text) and figure and not any(_date_at_start(c.text) for c in ln[:1]):
                    opening = _signed_balance(figure)
                    break
            if opening is not None:
                break
    if not raw_rows:
        raise StatementError("The statement's table was found but no transaction lines could be read from it")
    edges = sorted(desc_edges)
    full_width = edges[min(len(edges) - 1, int(len(edges) * 0.97))] if edges else 0.0

    st.rows, closing, chain = _prove(raw_rows, opening, full_width)
    if not st.rows:
        raise StatementError("No transaction lines with an amount could be read from this statement")
    st.opening_balance = opening if opening is not None else (
        (st.rows[0].balance - st.rows[0].amount if st.rows[0].direction == "credit" else st.rows[0].balance + st.rows[0].amount)
        if st.rows[0].balance is not None else None)
    st.closing_balance = closing
    st.balances_checked = chain
    if closing_printed is not None and chain and closing_printed != closing:
        raise StatementError(
            f"The closing balance read from the statement ({closing:,.2f}) differs from the one it prints "
            f"({closing_printed:,.2f}). Nothing was imported.")

    # lines after the last transaction: the statement's own totals
    printed_d, printed_c = _find_totals(trailer, st.total_debits, st.total_credits)
    st.printed_total_debits, st.printed_total_credits = printed_d, printed_c
    if printed_d is not None and printed_d != st.total_debits:
        raise StatementError(
            f"The debits read from the statement ({st.total_debits:,.2f}) differ from the total it prints "
            f"({printed_d:,.2f}). Nothing was imported.")
    if printed_c is not None and printed_c != st.total_credits:
        raise StatementError(
            f"The credits read from the statement ({st.total_credits:,.2f}) differ from the total it prints "
            f"({printed_c:,.2f}). Nothing was imported.")
    if not chain and printed_d is None:
        raise StatementError(
            "This statement has no running balance and no totals line to check the reading against, so it cannot be "
            "imported safely. Use the CSV import instead.")
    _statement_meta(pages, st)
    return st
