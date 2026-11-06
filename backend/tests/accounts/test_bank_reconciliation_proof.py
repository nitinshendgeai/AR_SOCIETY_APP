"""The last step of a bank reconciliation: proving the Bank Reconciliation Statement against the balance the bank's own
statement shows, and recording the bank's own items (charges, interest) in the books from the statement row."""
import io
from decimal import Decimal
from types import SimpleNamespace

from app.modules.accounts.services.bank_reconciliation import _ref_agrees, _same_ref
from tests.accounts.test_bank_reconciliation_books import (
    API, BILLING, _books, _brs, _cheque, _deposit, _entry_id, _import,
)
from tests.billing.bank_pdf import build_statement_pdf, row


def _rows(client, h, sid):
    r = client.get(f"{BILLING}/bank-reconciliation/society/{sid}", params={"limit": 500}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _pdf_import(client, h, sid, bank_id, rows, opening="100000.00"):
    r = client.post(f"{BILLING}/bank-reconciliation/society/{sid}/import",
                    params={"include_debits": "true", "bank_account_id": bank_id, "detail": "true"}, headers=h,
                    files={"statement": ("s.pdf", io.BytesIO(build_statement_pdf(rows, opening=opening)), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _statement_rows():
    return [
        row("02-Oct-2026", "NEFT SOCIETY MAINTENANCE", "UTR00001", credit="5000.00"),
        row("10-Oct-2026", "CHQ PAID 000123", "000123", debit="2000.00", mode="To Clg"),
        row("20-Oct-2026", "SMS CHARGES", "SMS1020", debit="25.00"),
        row("31-Oct-2026", "INT PAID TILL 30-09-2026", "INT1031", credit="100.00"),
    ]


def test_a_pdf_import_proves_the_reconciliation_and_the_banks_own_items_are_booked_from_the_rows(client, db):
    society, _f, admin, _m, L = _books(client, db, "bp1")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    _deposit(client, h, sid, L, 5000, "2026-10-01")
    _cheque(client, h, sid, L, 2000, "2026-10-05", ref="123")

    body = _pdf_import(client, h, sid, bank, _statement_rows())
    assert body["summary"]["statement_date"] == "2026-10-31"
    auto = client.post(f"{API}/bank-reconciliation/{sid}/auto-match", params={"account_id": bank}, headers=h).json()
    assert auto["matched"] == 2                               # the deposit by amount and date; the cheque 000123 = 123

    brs = _brs(client, h, sid, "2026-10-31", bank)
    assert brs["statement_balance"] == "103075.00" and brs["statement_balance_source"] == "pdf"
    assert brs["balance_per_bank"] == "103000.00" and brs["difference"] == "-75.00"
    # the difference is exactly the bank's own items the books do not have: -25 of charges, +100 of interest
    assert brs["unexplained"] == "0.00" and brs["status"] == "bank_items_to_book"
    assert {r["description"] for r in brs["bank_only_rows"]} == {"SMS CHARGES", "INT PAID TILL 30-09-2026"}

    for r in brs["bank_only_rows"]:
        ledger = L["bank_charges"] if r["direction"] == "debit" else L["interest_sb"]
        done = client.post(f"{API}/bank-reconciliation/{sid}/rows/{r['id']}/book", json={"account_id": ledger["id"]},
                           headers=h)
        assert done.status_code == 200, done.text
        assert done.json()["match_status"] == "matched"

    brs = _brs(client, h, sid, "2026-10-31", bank)
    assert brs["status"] == "reconciled" and brs["difference"] == "0.00" and brs["bank_only_rows"] == []
    assert brs["balance_per_books"] == "103075.00" and brs["uncleared_count"] == 0
    assert all(r["match_status"] == "matched" for r in _rows(client, h, sid))


def test_a_difference_the_bank_items_do_not_explain_is_shown_not_hidden(client, db):
    society, _f, admin, _m, L = _books(client, db, "bp2")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    _deposit(client, h, sid, L, 5000, "2026-10-01")             # recorded, the bank has not credited it yet

    r = client.get(f"{API}/bank-reconciliation/{sid}", params={"as_on": "2026-10-31", "account_id": bank}, headers=h)
    assert r.json()["status"] == "no_statement_balance" and r.json()["statement_balance"] is None

    brs = _brs_with(client, h, sid, bank, "2026-10-31", "100000")
    assert brs["balance_per_bank"] == "100000.00" and brs["status"] == "reconciled"   # books 105000, less the 5000 on its way

    brs = _brs_with(client, h, sid, bank, "2026-10-31", "99000")
    assert (brs["difference"], brs["unexplained"], brs["status"]) == ("1000.00", "1000.00", "difference")


def _brs_with(client, h, sid, bank, as_on, balance):
    r = client.get(f"{API}/bank-reconciliation/{sid}", params={"as_on": as_on, "account_id": bank,
                                                               "bank_balance": balance}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_typed_balance_can_be_kept_for_the_day(client, db):
    society, _f, admin, _m, L = _books(client, db, "bp3")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    r = client.put(f"{API}/bank-reconciliation/{sid}/statement-balance", headers=h,
                   json={"account_id": bank, "as_on": "2026-10-31", "balance": "100000"})
    assert r.status_code == 200, r.text
    brs = _brs(client, h, sid, "2026-10-31", bank)
    assert (brs["statement_balance"], brs["statement_balance_source"], brs["status"]) == ("100000.00", "manual", "reconciled")
    assert brs["latest_statement"] == {"as_on": "2026-10-31", "balance": "100000.00"}
    assert _brs(client, h, sid, "2026-10-30", bank)["statement_balance"] is None      # a balance belongs to its day
    future = client.put(f"{API}/bank-reconciliation/{sid}/statement-balance", headers=h,
                        json={"account_id": bank, "as_on": "2999-01-01", "balance": "1"})
    assert future.status_code == 422


def test_booking_a_row_is_refused_for_a_resident_vendor_or_cash_ledger_and_for_a_manager(client, db):
    society, _f, admin, manager, L = _books(client, db, "bp4")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    assert _import(client, sid, h, "Date,Description,Amount,Reference\n2026-10-20,SMS CHARGES,-25.00,SMS1\n",
                   include_debits="true", bank_account_id=bank).status_code == 201
    (stmt_row,) = _rows(client, h, sid)
    url = f"{API}/bank-reconciliation/{sid}/rows/{stmt_row['id']}/book"
    for key in ("members_dues", "sundry_creditors", "cash"):
        r = client.post(url, json={"account_id": L[key]["id"]}, headers=h)
        assert r.status_code == 422, (key, r.text)
    assert client.post(url, json={"account_id": L["bank_charges"]["id"]}, headers=manager["headers"]).status_code == 403
    assert _rows(client, h, sid)[0]["match_status"] == "unmatched"                  # nothing was booked

    ok = client.post(url, json={"account_id": L["bank_charges"]["id"], "narration": "SMS alert charges Q2"}, headers=h)
    assert ok.status_code == 200, ok.text
    again = client.post(url, json={"account_id": L["bank_charges"]["id"]}, headers=h)
    assert again.status_code == 409                                                  # a row is booked once
    brs = _brs(client, h, sid, "2026-10-31", bank)
    assert brs["balance_per_books"] == "99975.00" and brs["uncleared_count"] == 0    # cleared at once: the bank did it
    cleared = client.get(f"{API}/bank-reconciliation/{sid}/cleared", params={"account_id": bank}, headers=h).json()
    assert [(c["amount"], c["direction"], c["narration"]) for c in cleared] == [("25.00", "payment", "SMS alert charges Q2")]


def test_references_agree_by_cheque_number_or_utr_in_the_banks_text():
    bank_row = lambda ref, desc: SimpleNamespace(reference=ref, description=desc)
    assert _same_ref("000123", "123") and _same_ref("utr-77 ", "UTR77") and not _same_ref("0", "0") and not _same_ref("124", "123")
    assert _ref_agrees(bank_row("000123", "CHQ PAID"), "123")
    assert _ref_agrees(bank_row(None, "NEFT-HDFCN52026100312345-SOCIETY"), "HDFCN52026100312345")   # UTR inside the narration
    assert not _ref_agrees(bank_row(None, "NEFT-HDFCN52026100312345"), "1234")                       # too short to trust inside text
    assert not _ref_agrees(bank_row("999", "CHQ PAID"), "123")
