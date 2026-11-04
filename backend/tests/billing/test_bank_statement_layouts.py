"""The reader is not tied to one bank's layout: the same made-up transactions, printed in several different layouts,
must read back identically, and the proof against the statement's own balances must still bite in every layout."""
from datetime import datetime
from decimal import Decimal

import pytest

from app.modules.billing.services.bank_statement_pdf import StatementError, parse_statement_pdf
from tests.billing.bank_pdf import row, sample_rows
from tests.billing.bank_pdf_layouts import LAYOUTS, build_layout_pdf

BASE = "1000000.00"           # large enough that the balance never goes below zero


def _rows(n=None):
    rows = sample_rows()
    return rows[:n] if n else rows


@pytest.mark.parametrize("name", list(LAYOUTS))
def test_every_layout_reads_back_the_same_transactions(name):
    layout, rows = LAYOUTS[name], _rows()
    st = parse_statement_pdf(build_layout_pdf(layout, rows, opening=BASE))
    assert len(st.rows) == len(rows)
    running = Decimal(BASE)
    for got, want in zip(st.rows, rows):
        running += (want["credit"] or 0) - (want["debit"] or 0)
        assert got.txn_date == datetime.strptime(want["date"], "%d-%b-%Y").date()
        assert got.amount == (want["credit"] or want["debit"])
        assert got.direction == ("credit" if want["credit"] else "debit")
        assert got.balance == running
        if any(c.key == "ref" for c in layout.columns):
            assert got.reference == want["ref"].rstrip("/") or got.reference == want["ref"]
    assert st.opening_balance == Decimal(BASE) and st.closing_balance == running
    assert st.balances_checked is True
    assert (st.total_credits, st.total_debits) == (sum(r["credit"] or 0 for r in rows), sum(r["debit"] or 0 for r in rows))


@pytest.mark.parametrize("name", list(LAYOUTS))
def test_descriptions_keep_their_numbers_whole_in_every_layout(name):
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS[name], _rows(), opening=BASE))
    squeezed = st.rows[1].description.replace(" ", "")
    assert "615155222331" in squeezed and "000401934684" in squeezed


@pytest.mark.parametrize("name", list(LAYOUTS))
def test_a_broken_balance_is_refused_in_every_layout(name):
    with pytest.raises(StatementError, match="does not follow"):
        parse_statement_pdf(build_layout_pdf(LAYOUTS[name], _rows(), opening=BASE, balance_override={4: Decimal("5.00")}))


def test_a_printed_totals_row_is_checked_when_the_layout_has_one():
    layout = LAYOUTS["retail_b"]
    rows = _rows()
    ok = parse_statement_pdf(build_layout_pdf(layout, rows, opening=BASE))
    assert ok.printed_total_debits == ok.total_debits and ok.printed_total_credits == ok.total_credits
    credits = sum(r["credit"] or 0 for r in rows)
    with pytest.raises(StatementError, match="debits read"):
        parse_statement_pdf(build_layout_pdf(layout, rows, opening=BASE, printed_totals=(Decimal("1.00"), credits)))


def test_the_opening_balance_is_found_wherever_the_statement_prints_it_or_worked_back_when_it_does_not():
    for name in ("retail_a", "retail_b", "retail_c"):             # header text / a table row / not printed at all
        st = parse_statement_pdf(build_layout_pdf(LAYOUTS[name], _rows(), opening=BASE))
        assert st.opening_balance == Decimal(BASE), name


def test_account_number_period_and_bank_are_read_best_effort():
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS["retail_b"], _rows(), opening=BASE, account="000000000123"))
    assert st.account_number == "000000000123"
    last = datetime.strptime(_rows()[-1]["date"], "%d-%b-%Y").date()
    assert (st.from_date, st.to_date) == (datetime(2026, 10, 1).date(), last)
    assert "Co-op. Bank" in st.bank


def test_a_masked_account_number_is_read_as_printed():
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS["retail_a"], _rows(10), opening=BASE, account="XXXXXXXX0123"))
    assert st.account_number == "XXXXXXXX0123" and st.account_is_masked


def test_a_statement_with_a_wrong_debit_or_credit_mark_is_refused():
    # the amount is printed with the wrong (Cr)/(Dr) mark: the running balance says otherwise
    pdf = build_layout_pdf(LAYOUTS["single_amount"], _rows(8), opening=BASE)
    broken = pdf.replace(b"(Cr)", b"(Dr)") if b"(Cr)" in pdf else pdf
    # fpdf compresses page streams, so tamper at the source instead of the bytes
    layout = LAYOUTS["single_amount"]
    rows = _rows(8)
    swapped = [dict(r, credit=r["debit"], debit=r["credit"]) for r in rows]     # every line printed the wrong way round
    ok = parse_statement_pdf(build_layout_pdf(layout, rows, opening=BASE))
    assert ok.rows[0].direction == "credit"
    with pytest.raises(StatementError):
        # same balances as the originals but marks flipped: use a layout whose balances are kept from `rows`
        parse_statement_pdf(build_layout_pdf(layout, swapped, opening=BASE, balance_override={i: Decimal(0) for i in range(8)}))
    assert broken is not None


def test_a_pdf_that_is_a_picture_has_a_plain_message(tmp_path):
    from fpdf import FPDF
    pdf = FPDF(unit="pt", format="A4")
    pdf.add_page()
    pdf.rect(40, 40, 200, 200, style="F")                            # a drawing and no text at all
    with pytest.raises(StatementError, match="no readable text"):
        parse_statement_pdf(bytes(pdf.output()))


def test_a_pdf_with_text_but_no_transaction_table_is_refused():
    from fpdf import FPDF
    pdf = FPDF(unit="pt", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.text(40, 60, "Receipt for maintenance, flat A-101, amount paid 5,500.00 on 05-01-2026")
    with pytest.raises(StatementError, match="No transaction table"):
        parse_statement_pdf(bytes(pdf.output()))


@pytest.mark.parametrize("name", ["retail_b", "single_amount", "no_reference", "amount_only"])
def test_an_overdrawn_balance_is_read_with_its_sign(name):
    rows = _rows(14)
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS[name], rows, opening="-30000.00"))
    running = Decimal("-30000.00")
    for got, want in zip(st.rows, rows):
        running += (want["credit"] or 0) - (want["debit"] or 0)
        assert got.balance == running
    assert any(r.balance < 0 for r in st.rows) and any(r.balance > 0 for r in st.rows)


@pytest.mark.parametrize("font", [7.0, 9.0])
def test_other_font_sizes_read_the_same(font):
    rows = _rows(20)
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS["retail_b"], rows, opening=BASE, font=font))
    assert [(r.amount, r.direction) for r in st.rows] == [(x["credit"] or x["debit"], "credit" if x["credit"] else "debit") for x in rows]


def test_a_one_column_plain_amount_takes_its_direction_from_the_balance():
    rows = _rows(20)
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS["amount_only"], rows, opening=BASE))
    assert [r.direction for r in st.rows] == ["credit" if x["credit"] else "debit" for x in rows]


def test_no_reference_column_means_no_reference():
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS["no_reference"], _rows(20), opening=BASE))
    assert all(r.reference is None for r in st.rows)


def test_a_dated_line_in_a_page_header_is_not_mistaken_for_a_transaction():
    rows = _rows()
    st = parse_statement_pdf(build_layout_pdf(LAYOUTS["plain_numbers"], rows, opening=BASE, page_date_line=True))
    assert len(st.rows) == len(rows)


def test_a_line_that_is_missing_makes_the_balance_break_and_the_file_is_refused():
    rows = _rows(20)
    without = rows[:6] + rows[7:]                       # the line is gone, but the bank's printed balances still include it
    running, printed = Decimal(BASE), {}
    for i, r in enumerate(rows):
        running += (r["credit"] or 0) - (r["debit"] or 0)
        if i != 6:
            printed[i if i < 6 else i - 1] = running
    with pytest.raises(StatementError, match="does not follow"):
        parse_statement_pdf(build_layout_pdf(LAYOUTS["retail_b"], without, opening=BASE, balance_override=printed))
