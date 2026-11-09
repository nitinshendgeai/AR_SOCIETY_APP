"""Each statement line is stored once and listed once, under the bank it belongs to: a statement imported twice (or with
and without the bank chosen) adds nothing the second time, and a row saved with no bank is not listed under every bank."""
from app.modules.billing.models.billing import BankStatementEntry
from tests.accounts.test_bank_reconciliation_books import API, BILLING, _books, _brs, _import
from tests.billing.bank_pdf import build_statement_pdf, row

CSV = "Date,Description,Amount,Reference\n2026-10-02,NEFT MAINTENANCE,5000.00,UTR1\n2026-10-20,SMS CHARGES,-25.00,SMS1\n"


def _rows_of(client, h, sid, bank, **params):
    r = client.get(f"{API}/bank-reconciliation/{sid}/rows", params={"account_id": bank, **params}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _second_bank(client, h, sid, L):
    r = client.post(f"{API}/ledgers", headers=h, json={
        "society_id": sid, "group_id": L["bank"]["group_id"], "name": "Savings Account", "is_bank": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_the_same_csv_imported_twice_adds_nothing_the_second_time(client, db):
    society, _f, admin, _m, L = _books(client, db, "once1")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    first = _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank, detail="true")
    assert first.status_code == 201 and first.json()["summary"]["imported"] == 2
    again = _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank, detail="true")
    assert again.status_code == 201, again.text
    assert again.json()["summary"] == {"file_type": "csv", "imported": 0, "skipped_duplicates": 2} and again.json()["entries"] == []
    assert len(_rows_of(client, h, sid, bank)) == 2


def test_with_one_bank_a_statement_belongs_to_it_whether_or_not_the_bank_is_chosen(client, db):
    society, _f, admin, _m, L = _books(client, db, "once2")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    assert _import(client, sid, h, CSV, include_debits="true").status_code == 201           # no bank chosen
    assert _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank).status_code == 201   # chosen
    stored = db.query(BankStatementEntry).filter(BankStatementEntry.society_id == society.id).all()
    assert len(stored) == 2 and {str(r.bank_account_id) for r in stored} == {bank}          # once each, against the bank


def test_a_line_saved_with_no_bank_is_not_stored_again_when_the_bank_is_chosen_later(client, db):
    society, _f, admin, _m, L = _books(client, db, "once3")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    other = _second_bank(client, h, sid, L)                       # two banks: no bank chosen means no bank known
    assert _import(client, sid, h, CSV, include_debits="true").status_code == 201
    assert {r.bank_account_id for r in db.query(BankStatementEntry).filter(BankStatementEntry.society_id == society.id)} == {None}
    again = _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank, detail="true")
    assert again.json()["summary"]["imported"] == 0 and again.json()["summary"]["skipped_duplicates"] == 2
    assert len(db.query(BankStatementEntry).filter(BankStatementEntry.society_id == society.id).all()) == 2
    assert other != bank


def test_a_row_with_no_bank_is_listed_once_under_the_default_bank_only(client, db):
    society, _f, admin, _m, L = _books(client, db, "once4")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    other = _second_bank(client, h, sid, L)
    assert _import(client, sid, h, CSV, include_debits="true").status_code == 201           # saved with no bank
    assert len(_rows_of(client, h, sid, bank)) == 2                                          # the default bank has them
    assert _rows_of(client, h, sid, other) == []                                             # the other bank does not
    # and the reconciliation of the other bank does not count them either
    assert _brs(client, h, sid, "2026-10-31", other)["unmatched_statement_rows"] == 0
    assert _brs(client, h, sid, "2026-10-31", other)["bank_only_rows"] == []
    assert _brs(client, h, sid, "2026-10-31", bank)["unmatched_statement_rows"] == 2


def test_a_copy_with_no_bank_is_hidden_when_the_same_line_is_stored_against_a_bank(client, db):
    """Statements imported twice by an older version: once without the bank, once with it."""
    society, _f, admin, _m, L = _books(client, db, "once5")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    _second_bank(client, h, sid, L)
    assert _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank).status_code == 201
    for r in db.query(BankStatementEntry).filter(BankStatementEntry.society_id == society.id).all():
        db.add(BankStatementEntry(society_id=r.society_id, txn_date=r.txn_date, description=r.description,
                                  reference=r.reference, amount=r.amount, direction=r.direction, bank_account_id=None))
    db.commit()
    assert db.query(BankStatementEntry).filter(BankStatementEntry.society_id == society.id).count() == 4
    shown = _rows_of(client, h, sid, bank)
    assert sorted(r["description"] for r in shown) == ["NEFT MAINTENANCE", "SMS CHARGES"]   # each line once
    assert _brs(client, h, sid, "2026-10-31", bank)["unmatched_statement_rows"] == 4       # the report still counts what is stored


def test_the_rows_can_be_listed_by_status_and_are_newest_first(client, db):
    society, _f, admin, _m, L = _books(client, db, "once6")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    assert _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank).status_code == 201
    rows = _rows_of(client, h, sid, bank)
    assert [r["txn_date"] for r in rows] == ["2026-10-20", "2026-10-02"]
    ignored = client.post(f"{BILLING}/bank-reconciliation/{rows[0]['id']}/ignore", json={"reason": "not ours"}, headers=h)
    assert ignored.status_code == 200, ignored.text
    assert [r["description"] for r in _rows_of(client, h, sid, bank, match_status="ignored")] == ["SMS CHARGES"]
    assert [r["description"] for r in _rows_of(client, h, sid, bank, match_status="unmatched")] == ["NEFT MAINTENANCE"]
    assert client.get(f"{API}/bank-reconciliation/{sid}/rows", params={"match_status": "bogus"}, headers=h).status_code == 422


def test_statement_rows_can_be_read_page_by_page(client, db):
    """The app pages through `skip`/`limit`; the pages together are the whole list, each row once."""
    society, _f, admin, _m, L = _books(client, db, "once_pages")
    h, sid, bank = admin["headers"], str(society.id), L["bank"]["id"]
    assert _import(client, sid, h, CSV, include_debits="true", bank_account_id=bank).status_code == 201
    everything = _rows_of(client, h, sid, bank)
    assert len(everything) == 2
    first = _rows_of(client, h, sid, bank, limit=1)
    second = _rows_of(client, h, sid, bank, limit=1, skip=1)
    assert [r["id"] for r in first + second] == [r["id"] for r in everything]
    assert _rows_of(client, h, sid, bank, limit=1, skip=2) == []
