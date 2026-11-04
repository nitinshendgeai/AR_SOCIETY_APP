"""Reading a bank's Account Statement PDF: the table is read by position, then proved against the statement's own
running balances and printed totals. The PDFs are built by tests/billing/bank_pdf.py from made-up data."""
from datetime import date
from decimal import Decimal

import pytest

from app.modules.billing.services.bank_statement_pdf import StatementError, parse_statement_pdf
from tests.billing.bank_pdf import build_statement_pdf, inr, row, sample_rows


def test_indian_digit_grouping_helper():
    assert inr(Decimal("5000")) == "5,000.00"
    assert inr(Decimal("248023")) == "2,48,023.00"
    assert inr(Decimal("13315720")) == "1,33,15,720.00"
    assert inr(Decimal("295")) == "295.00"


def test_every_line_is_read_with_its_direction_amount_and_reference():
    st = parse_statement_pdf(build_statement_pdf(sample_rows()))
    assert len(st.rows) == len(sample_rows())
    first = st.rows[0]
    assert (first.txn_date, first.value_date) == (date(2026, 10, 1), date(2026, 10, 1))
    assert (first.direction, first.amount, first.reference, first.mode) == ("credit", Decimal("5000.00"), "70000001", "By Trf")
    cheque = st.rows[2]
    assert cheque.reference == "70000003/271" and cheque.amount == Decimal("15000.00")      # cheque number kept
    returned = st.rows[3]
    assert (returned.direction, returned.amount, returned.mode) == ("debit", Decimal("295.00"), "To Trf")
    big = st.rows[6]
    assert (big.direction, big.amount) == ("debit", Decimal("248023.00"))                  # Indian grouping, debit column
    cash = st.rows[4]
    assert (cash.direction, cash.mode, cash.description) == ("debit", "To Csh", "TO CASH SELF")


def test_the_statement_header_totals_and_balances_are_read():
    rows = sample_rows()
    st = parse_statement_pdf(build_statement_pdf(rows, account="000000000123"))
    assert st.account_number == "000000000123" and st.bank.startswith("Sample District")
    assert (st.from_date, st.to_date) == (date(2026, 10, 1), date(2026, 10, 31))
    assert st.opening_balance == Decimal("100000.00")
    credits = sum(r["credit"] or 0 for r in rows)
    debits = sum(r["debit"] or 0 for r in rows)
    assert (st.total_credits, st.total_debits) == (credits, debits)
    assert (st.printed_total_credits, st.printed_total_debits) == (credits, debits)         # checked against the PDF's own line
    assert st.closing_balance == Decimal("100000.00") + credits - debits


def test_a_statement_over_several_pages_is_read_whole():
    pdf = build_statement_pdf(sample_rows())
    from pdfminer.pdfpage import PDFPage
    import io
    assert len(list(PDFPage.get_pages(io.BytesIO(pdf)))) >= 3          # table pages plus the totals page
    assert len(parse_statement_pdf(pdf).rows) == len(sample_rows())


def test_lines_the_bank_wrapped_are_joined_back_together():
    st = parse_statement_pdf(build_statement_pdf(sample_rows()))
    # Where the bank cut a line is not always where a space was, so spacing is best-effort; the numbers are not.
    def squeezed(i):
        return st.rows[i].description.replace(" ", "")
    assert squeezed(0) == "/UTIBN62026100126722404/NEFT/PRAVINKRISHNARAWOOLUTIB0000572///"
    assert squeezed(1) == "UPI/CR/615155222331/ICIC/TESTPAYERONE/payer1@ptyes/000401934684/000000000123"
    assert squeezed(3) == "/OWCLG_CTSRETURN/0441106000000127/-000042"
    assert "615155222331" in st.rows[1].description and "0441106000000127" in st.rows[3].description     # whole numbers
    assert st.rows[5].description.startswith("IMPS/627616809411/")


def test_a_statement_without_a_totals_line_is_still_checked_by_its_running_balance():
    st = parse_statement_pdf(build_statement_pdf(sample_rows(), printed_totals=False))
    assert st.printed_total_debits is None and len(st.rows) == len(sample_rows())


def test_a_balance_that_does_not_follow_is_refused_whole():
    with pytest.raises(StatementError, match="does not follow"):
        parse_statement_pdf(build_statement_pdf(sample_rows(), balance_override={3: Decimal("1.00")}))


def test_totals_that_differ_from_the_lines_are_refused():
    credits = sum(r["credit"] or 0 for r in sample_rows())
    with pytest.raises(StatementError, match="debits read"):
        parse_statement_pdf(build_statement_pdf(sample_rows(), printed_totals=(Decimal("1.00"), credits)))
    debits = sum(r["debit"] or 0 for r in sample_rows())
    with pytest.raises(StatementError, match="credits read"):
        parse_statement_pdf(build_statement_pdf(sample_rows(), printed_totals=(debits, Decimal("1.00"))))


def test_files_that_are_not_this_statement_are_refused_with_a_plain_message():
    with pytest.raises(StatementError, match="not a PDF"):
        parse_statement_pdf(b"Date,Description,Amount\n2026-01-01,x,1\n")
    with pytest.raises(StatementError, match="could not be read"):
        parse_statement_pdf(b"%PDF-1.4\nthis is not really a pdf")
    # a statement does not need a particular title: only a table of dated lines with amounts and balances
    assert len(parse_statement_pdf(build_statement_pdf(sample_rows(), drop_title=True)).rows) == len(sample_rows())
    from app.modules.billing.services.bank_statement_pdf import MAX_PDF_BYTES
    with pytest.raises(StatementError, match="too large"):
        parse_statement_pdf(b"%PDF-" + b"0" * MAX_PDF_BYTES)
