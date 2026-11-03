"""Builds a bank "Account Statement" PDF laid out like the Crystal-Reports statement a co-operative bank prints
(header block, a boxed table of TXN Date / Value Date / Description / ReferenceNo / Tr. Mode / Branch Code / Debit /
Credit / Balance with the header repeated on every page, descriptions wrapped at a fixed width, a footer on every
page and a closing "Summation of Debits and Credits" line). Everything in it is made up: no real person, account or
bank. Used to test bank_statement_pdf.py without keeping anybody's real statement in the repository.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from fpdf import FPDF

FONT = 8
LINE = 11.2
DESC_X, DESC_W = 146.3, 72.6
CREDIT_RIGHT, DEBIT_RIGHT, BALANCE_RIGHT = 494.8, 429.8, 572.0
TABLE_TOP = 519.0                         # baseline of the column-header row, measured from the top of the page


def inr(value: Decimal) -> str:
    """12345678.9 -> 1,23,45,678.90 (Indian digit grouping, as banks here print)."""
    whole, frac = f"{abs(value):.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail]) + "." + frac


def money(value) -> Decimal:
    return Decimal(str(value))


def row(day: str, desc: str, ref: str, credit=None, debit=None, mode: Optional[str] = None, time: str = "10:02:13"):
    return {"date": day, "desc": desc, "ref": ref, "credit": money(credit) if credit is not None else None,
            "debit": money(debit) if debit is not None else None, "mode": mode or ("By Trf" if credit else "To Trf"),
            "time": time}


def build_statement_pdf(rows: List[dict], opening="100000.00", account="000000000123", from_date="01-Oct-2026",
                        to_date="31-Oct-2026", printed_totals: object = True,
                        balance_override: Optional[dict] = None, drop_title: bool = False,
                        bank: str = "Sample District Co-op. Bank Ltd") -> bytes:
    """printed_totals: True = the correct totals, False = no totals line, (debits, credits) = those (wrong) numbers.
    balance_override: {row index: balance printed for that row} to make a statement that does not add up."""
    pdf = FPDF(unit="pt", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_font("Helvetica", size=FONT)

    def put(x, y, txt, bold=False, right=None):
        pdf.set_font("Helvetica", style="B" if bold else "", size=FONT)
        if right is not None:
            x = right - pdf.get_string_width(txt)
        pdf.text(x, y, txt)

    def wrap(text: str) -> List[str]:
        """The bank wraps at a fixed pixel width: by words when it can, in the middle of a word when it must."""
        out, cur = [], ""
        for token in text.split(" "):
            candidate = (cur + " " + token) if cur else token
            if pdf.get_string_width(candidate) <= DESC_W:
                cur = candidate
                continue
            if cur:
                out.append(cur)
                cur = ""
            while pdf.get_string_width(token) > DESC_W:
                cut = len(token)
                while pdf.get_string_width(token[:cut]) > DESC_W:
                    cut -= 1
                out.append(token[:cut])
                token = token[cut:]
            cur = token
        if cur:
            out.append(cur)
        return out

    balance = money(opening)
    printed = []
    for i, r in enumerate(rows):
        balance = balance + (r["credit"] or 0) - (r["debit"] or 0)
        shown = (balance_override or {}).get(i, balance)
        printed.append((r, wrap(r["desc"]), shown))
    total_debits = sum((r["debit"] or 0 for r in rows), Decimal(0))
    total_credits = sum((r["credit"] or 0 for r in rows), Decimal(0))

    def page_frame(n: int, total: int, first: bool) -> float:
        pdf.add_page()
        if first:
            put(160.8, 44, bank, bold=True)
            put(18, 84, "Branch:", bold=True)
            put(58.5, 84, "001-SAMPLE BRANCH")
            put(416.9, 84, "Report No.: TB-R-014", bold=True)
        if not drop_title:
            put(216.7, 100 if first else 38, "Account Statement", bold=True)
        if first:
            for label, value, y in (("Chart of Account :", "CURRENT SOCIETY [0000]", 119),
                                    ("Account Number :", account, 145), ("Customer Name:", "SAMPLE HOUSING SOCIETY LIMITED", 157)):
                put(19.5, y, label, bold=True)
                put(132.8, y, value, bold=True)
            put(19.5, 132, "From Date :", bold=True)
            put(132.8, 132, from_date, bold=True)
            put(263.5, 132, "To Date :", bold=True)
            put(313.0, 132, to_date, bold=True)
        top = TABLE_TOP if first else 62.0
        pdf.rect(18, top - 24, 560, 400 if False else 0.1)
        for x, label in ((235.5, "ReferenceNo"), (340.7, "Branch")):
            put(x, top - 6, label, bold=True)
        for x, label, right in ((28.8, "TXN Date", None), (89.5, "Value Date", None), (163.8, "Description", None),
                                (298.6, "Tr. Mode", None), (391.4, "Debit", None), (460.9, "Credit", None),
                                (539.1, "Balance", None)):
            put(x, top, label, bold=True)
        put(239.1, top + 6, "/ChequeNo", bold=True)
        put(345.5, top + 6, "Code", bold=True)
        put(24, 800, "Printed by '0000' on 03-Nov-2026 at 12:33", bold=True)
        put(545, 810, f"Page {n} of {total}", bold=True)
        put(24, 822, "Trust Bank", bold=True)
        return top + 22

    # lay the rows out page by page
    pages: List[List[tuple]] = [[]]
    used, limit = 0.0, 640.0 - (TABLE_TOP - 62.0)
    first_limit = 640.0 - TABLE_TOP + 62.0 - 40
    for item in printed:
        h = max(len(item[1]), 2 if item[0]["time"] else 1) * LINE + 10
        cap = first_limit if len(pages) == 1 else limit
        if used + h > cap and pages[-1]:
            pages.append([])
            used = 0.0
        pages[-1].append(item)
        used += h
    has_totals_page = printed_totals is not False
    total_pages = len(pages) + (1 if has_totals_page else 0)

    for n, chunk in enumerate(pages, start=1):
        y = page_frame(n, total_pages, first=(n == 1))
        if n == 1:
            put(24, y, from_date)
            put(146.3, y, "Opening Balance", bold=False)
            put(0, y, f"{inr(money(opening))} Cr", right=BALANCE_RIGHT)
            y += 34
        for r, desc_lines, shown in chunk:
            put(24, y, r["date"])
            put(84.8, y, r["date"])
            if r["time"]:
                put(91.9, y + LINE, r["time"])
            for k, text in enumerate(desc_lines):
                put(DESC_X, y + k * LINE, text)
            put(236.0, y, r["ref"] + ("/" if "/" not in r["ref"] else ""))
            put(306.5, y, r["mode"])
            put(343.5, y, "001")
            if r["debit"] is not None:
                put(0, y, inr(r["debit"]), right=DEBIT_RIGHT)
            if r["credit"] is not None:
                put(0, y, inr(r["credit"]), right=CREDIT_RIGHT)
            put(0, y, f"{inr(shown)} {'Cr' if shown >= 0 else 'Dr'}", right=BALANCE_RIGHT)
            y += max(len(desc_lines), 2 if r["time"] else 1) * LINE + 10

    if has_totals_page:
        pdf.add_page()
        if not drop_title:
            put(216.7, 38, "Account Statement", bold=True)
        d, c = (total_debits, total_credits) if printed_totals is True else printed_totals
        put(24, 90, "Voucher :", bold=True)
        put(71, 90, str(len(rows)), bold=True)
        put(104, 90, "Summation of Debits and Credits...", bold=True)
        put(0, 90, inr(money(d)), bold=True, right=416.8)
        put(0, 90, inr(money(c)), bold=True, right=CREDIT_RIGHT)
        put(0, 90, f"{inr(balance)} Cr", bold=True, right=BALANCE_RIGHT)
        put(24, 110, "Note : Unless a Constituent notifies Bank / Society immediately of any discrepancy", bold=True)
        put(24, 800, "This is a system-generated report. No Signature is Required.")
        put(24, 812, "Printed by '0000' on 03-Nov-2026 at 12:33", bold=True)
        put(545, 822, f"Page {total_pages} of {total_pages}", bold=True)
    return bytes(pdf.output())


def sample_rows() -> List[dict]:
    """A month of made-up activity: UPI and NEFT credits with wrapped descriptions, a cheque credit, cash-out and
    cheque-return debits, enough lines to run onto a second page."""
    rows = [
        row("01-Oct-2026", "/UTIBN62026100126722404/NEFT/PRAVIN KRISHNA RAWOOLUTIB0000572///", "70000001", credit="5000.00"),
        row("01-Oct-2026", "UPI/ CR/ 615155222331/ ICIC/ TEST PAYER ONE/ payer1@ptyes/ 000401934684/ 000000000123", "70000002", credit="15000.00", time="21:34:39"),
        row("02-Oct-2026", "By O/W Clg BY CLG TEST PAYER TWO", "70000003/271", credit="15000.00", time="16:43:23"),
        row("03-Oct-2026", "/OW CLG_CTS RETURN/0441106000000127/-000042", "70000004", debit="295.00", mode="To Trf"),
        row("03-Oct-2026", "TO CASH SELF", "70000005/12961", debit="15000.00", mode="To Csh"),
        row("04-Oct-2026", "IMPS/627616809411/DEEPAK TESTER/SampleBank/158097989897/Inward", "70000006", credit="15000.00"),
        row("05-Oct-2026", "To I/W Clg M 9 ENTERPRISES", "70000007/12966", debit="248023.00", mode="To Trf"),
    ]
    for k in range(8, 40):                          # more of the same, so the statement runs over several pages
        rows.append(row(f"{min(5 + k // 3, 30):02d}-Oct-2026", f"UPI/ CR/ 6276{k:08d}/ SBIN/ TEST PAYER {k}/ payer{k}@oksbi/ 0000{k:04d}/ 000000000123",
                        f"700001{k:02d}", credit="15000.00" if k % 5 else "13000.00", time=f"{9 + k % 10}:{k:02d}:01"))
    return rows
