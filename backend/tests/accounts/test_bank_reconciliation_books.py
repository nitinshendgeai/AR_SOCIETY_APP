"""Bank reconciliation against the books: the Bank Reconciliation Statement (what the books say, less what the bank
has not cleared yet, is what the bank statement shows), clearing lines by hand or by matching bank statement rows
(credits and debits), and the link with residents' online payments."""
import io
from datetime import date
from decimal import Decimal

from tests.accounts.test_reports import API, _ledgers, _voucher
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

BILLING = "/api/v1/billing"


def _books(client, db, tag, opening="100000"):
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    admin = make_user(db, f"admin@{tag}.com", role="Society Admin")
    h, sid = admin["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    r = client.patch(f"{API}/ledgers/{L['bank']['id']}", json={"opening_balance": opening}, headers=h)
    assert r.status_code == 200, r.text
    return society, flat1, admin, manager, L


def _deposit(client, h, sid, L, amount, on, ref=None):
    return _voucher(client, h, sid, "receipt", on, [
        {"account_id": L["bank"]["id"], "debit": str(amount)},
        {"account_id": L["misc_income"]["id"], "credit": str(amount)}]) if ref is None else _with_ref(
        client, h, sid, "receipt", on, ref, [
            {"account_id": L["bank"]["id"], "debit": str(amount)},
            {"account_id": L["misc_income"]["id"], "credit": str(amount)}])


def _cheque(client, h, sid, L, amount, on, ref=None):
    entries = [{"account_id": L["audit_fees"]["id"], "debit": str(amount)},
               {"account_id": L["bank"]["id"], "credit": str(amount)}]
    return _with_ref(client, h, sid, "payment", on, ref, entries) if ref else _voucher(
        client, h, sid, "payment", on, entries)


def _with_ref(client, h, sid, vtype, on, ref, entries):
    r = client.post(f"{API}/vouchers", json={"society_id": sid, "voucher_type": vtype, "voucher_date": on,
                                              "reference": ref, "entries": entries}, headers=h)
    assert r.status_code == 201, r.text
    v = r.json()
    if v.get("approval_status") == "pending":
        assert client.post(f"{API}/vouchers/{v['id']}/approve", json={}, headers=h).status_code == 200
    return v


def _brs(client, h, sid, as_on, account_id=None):
    params = {"as_on": as_on, **({"account_id": account_id} if account_id else {})}
    r = client.get(f"{API}/bank-reconciliation/{sid}", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _entry_id(brs, voucher_number):
    for line in brs["payments_not_cleared"] + brs["deposits_not_cleared"]:
        if line["voucher_number"] == voucher_number:
            return line["entry_id"]
    raise AssertionError(f"{voucher_number} is not on the statement")


def _clear(client, h, sid, entry_ids, on, expect=200):
    r = client.post(f"{API}/bank-reconciliation/{sid}/clear", json={"entry_ids": entry_ids, "cleared_date": on},
                    headers=h)
    assert r.status_code == expect, r.text
    return r


def _import(client, sid, h, csv_text, **params):
    return client.post(f"{BILLING}/bank-reconciliation/society/{sid}/import", params=params, headers=h,
                       files={"statement": ("statement.csv", io.BytesIO(csv_text.encode()), "text/csv")})


def test_statement_starts_with_the_books_and_ends_with_what_the_bank_shows(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br1")
    h, sid = admin["headers"], str(society.id)
    dep = _deposit(client, h, sid, L, 5000, "2025-01-05")
    chq = _cheque(client, h, sid, L, 2000, "2025-01-06")

    brs = _brs(client, h, sid, "2025-01-31")
    assert brs["balance_per_books"] == "103000.00"
    assert brs["deposits_not_cleared_total"] == "5000.00" and brs["payments_not_cleared_total"] == "2000.00"
    # The bank still shows only the opening ₹1,00,000: 103000 + 2000 (cheque not presented) - 5000 (not credited)
    assert brs["balance_per_bank"] == "100000.00"

    _clear(client, h, sid, [_entry_id(brs, dep["voucher_number"])], "2025-01-08")
    brs = _brs(client, h, sid, "2025-01-31")
    assert brs["deposits_not_cleared"] == [] and brs["balance_per_bank"] == "105000.00"

    _clear(client, h, sid, [_entry_id(brs, chq["voucher_number"])], "2025-02-10")
    assert _brs(client, h, sid, "2025-01-31")["balance_per_bank"] == "105000.00"   # cleared after that date
    done = _brs(client, h, sid, "2025-02-28")
    assert done["payments_not_cleared"] == [] and done["balance_per_bank"] == done["balance_per_books"] == "103000.00"
    assert done["uncleared_count"] == 0


def test_the_statement_is_as_on_a_date(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br2")
    h, sid = admin["headers"], str(society.id)
    _cheque(client, h, sid, L, 700, "2025-02-10")
    early = _brs(client, h, sid, "2025-02-01")
    assert early["balance_per_books"] == "100000.00" and early["payments_not_cleared"] == []
    late = _brs(client, h, sid, "2025-02-15")
    assert late["balance_per_books"] == "99300.00" and late["balance_per_bank"] == "100000.00"
    assert late["payments_not_cleared"][0]["days_pending"] == 5


def test_a_payment_waiting_for_approval_is_not_on_the_statement(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br3")
    h, sid = admin["headers"], str(society.id)
    r = client.post(f"{API}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": "2025-01-06",
        "entries": [{"account_id": L["audit_fees"]["id"], "debit": "900"},
                    {"account_id": L["bank"]["id"], "credit": "900"}]})
    assert r.json()["approval_status"] == "pending"
    brs = _brs(client, h, sid, "2025-01-31")
    assert brs["payments_not_cleared"] == [] and brs["balance_per_books"] == "100000.00"


def test_clearing_rules(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br4")
    h, sid = admin["headers"], str(society.id)
    chq = _cheque(client, h, sid, L, 2000, "2025-01-06")
    cash = _voucher(client, h, sid, "payment", "2025-01-06", [
        {"account_id": L["audit_fees"]["id"], "debit": "300"}, {"account_id": L["cash"]["id"], "credit": "300"}])
    entry = _entry_id(_brs(client, h, sid, "2025-01-31"), chq["voucher_number"])

    assert "earlier" in _clear(client, h, sid, [entry], "2025-01-05", 422).json()["detail"]
    assert _clear(client, h, sid, [entry], "2999-01-01", 422)
    # Cash has no bank statement
    cash_entry = next(e["id"] for e in client.get(f"{API}/vouchers/{cash['id']}", headers=h).json()["entries"]
                      if e["account_id"] == L["cash"]["id"])
    assert "bank" in _clear(client, h, sid, [cash_entry], "2025-01-07", 422).json()["detail"].lower()
    assert _clear(client, h, sid, [entry], "2025-01-07").json() == {"cleared": 1}
    assert client.post(f"{API}/bank-reconciliation/{sid}/unclear", json={"entry_ids": [entry]},
                       headers=h).json() == {"uncleared": 1}
    assert _brs(client, h, sid, "2025-01-31")["payments_not_cleared_total"] == "2000.00"


def test_a_cancelled_voucher_leaves_the_statement(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br5")
    h, sid = admin["headers"], str(society.id)
    chq = _cheque(client, h, sid, L, 2000, "2025-01-06")
    assert client.post(f"{API}/vouchers/{chq['id']}/cancel", json={"reason": "Wrong amount"},
                       headers=h).status_code == 200
    brs = _brs(client, h, sid, "2025-01-31")
    assert brs["payments_not_cleared"] == [] and brs["balance_per_books"] == "100000.00"


def test_only_admin_or_committee_clear_lines(client, db):
    society, _flat, admin, manager, L = _books(client, db, "br6")
    h, sid = admin["headers"], str(society.id)
    chq = _cheque(client, h, sid, L, 2000, "2025-01-06")
    entry = _entry_id(_brs(client, h, sid, "2025-01-31"), chq["voucher_number"])
    assert _clear(client, manager["headers"], sid, [entry], "2025-01-07", 403)
    assert client.get(f"{API}/bank-reconciliation/{sid}", headers=manager["headers"]).status_code == 200


def test_statement_rows_match_the_books_both_ways(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br7")
    h, sid = admin["headers"], str(society.id)
    dep = _deposit(client, h, sid, L, 5000, "2025-01-05", ref="NEFT-778")
    chq = _cheque(client, h, sid, L, 2000, "2025-01-06", ref="000123")
    _cheque(client, h, sid, L, 2000, "2025-01-07", ref="000124")           # same amount, another cheque

    csv_text = ("Date,Description,Reference,Debit,Credit\n"
                "2025-01-09,NEFT CR SOCIETY,NEFT-778,,5000.00\n"
                "2025-01-20,CHQ 000123,000123,2000.00,\n")
    r = _import(client, sid, h, csv_text, bank_account_id=L["bank"]["id"])
    assert r.status_code == 201, r.text
    rows = {x["direction"]: x for x in r.json()}
    assert set(rows) == {"credit", "debit"} and rows["debit"]["bank_account_id"] == L["bank"]["id"]

    # The debit row could be either cheque; the one whose reference agrees comes first
    sugg = client.get(f"{API}/bank-reconciliation/{sid}/rows/{rows['debit']['id']}/suggestions", headers=h).json()
    assert [s["voucher_number"] for s in sugg][0] == chq["voucher_number"] and len(sugg) == 2
    assert sugg[0]["reference_matches"] and not sugg[1]["reference_matches"]

    base = f"{API}/bank-reconciliation/{sid}/rows"
    # A deposit can't be matched to a payment, nor an amount to a different amount
    wrong = next(s for s in sugg if not s["reference_matches"])
    r = client.post(f"{base}/{rows['credit']['id']}/match", json={"entry_id": wrong["entry_id"]}, headers=h)
    assert r.status_code == 422, r.text
    ok = client.post(f"{base}/{rows['debit']['id']}/match", json={"entry_id": sugg[0]["entry_id"]}, headers=h)
    assert ok.status_code == 200 and ok.json()["match_status"] == "matched"
    assert client.post(f"{base}/{rows['debit']['id']}/match", json={"entry_id": sugg[0]["entry_id"]},
                       headers=h).status_code == 409

    deposit_entry = _entry_id(_brs(client, h, sid, "2025-01-31"), dep["voucher_number"])
    done = client.post(f"{base}/{rows['credit']['id']}/match", json={"entry_id": deposit_entry}, headers=h)
    assert done.status_code == 200, done.text
    brs = _brs(client, h, sid, "2025-01-31")
    assert brs["deposits_not_cleared"] == [] and [x["voucher_number"] for x in brs["payments_not_cleared"]] != []
    assert brs["unmatched_statement_rows"] == 0
    cleared = {c["voucher_number"]: c["cleared_date"] for c in client.get(
        f"{API}/bank-reconciliation/{sid}/cleared", headers=h).json()}
    assert cleared == {dep["voucher_number"]: "2025-01-09", chq["voucher_number"]: "2025-01-20"}

    # Taking the match back puts the line on the statement again
    back = client.post(f"{base}/{rows['debit']['id']}/unmatch", headers=h)
    assert back.status_code == 200 and back.json()["match_status"] == "unmatched"
    assert chq["voucher_number"] in [x["voucher_number"] for x in _brs(client, h, sid, "2025-01-31")["payments_not_cleared"]]


def test_auto_match_takes_only_the_unambiguous(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br8")
    h, sid = admin["headers"], str(society.id)
    dep = _deposit(client, h, sid, L, 5000, "2025-01-05", ref="NEFT-778")
    _cheque(client, h, sid, L, 2000, "2025-01-06")                          # no reference
    _cheque(client, h, sid, L, 2000, "2025-01-07")                          # indistinguishable from the one above
    csv_text = ("Date,Description,Reference,Debit,Credit\n"
                "2025-01-07,NEFT CR,neft-778,,5000.00\n"
                "2025-01-12,CHQ,,2000.00,\n")
    assert _import(client, sid, h, csv_text, bank_account_id=L["bank"]["id"]).status_code == 201
    r = client.post(f"{API}/bank-reconciliation/{sid}/auto-match", headers=h)
    assert r.status_code == 200 and r.json() == {"matched": 1, "left_for_a_person": 1}
    brs = _brs(client, h, sid, "2025-01-31")
    assert brs["deposits_not_cleared"] == [] and len(brs["payments_not_cleared"]) == 2
    assert dep["voucher_number"] in {c["voucher_number"] for c in client.get(
        f"{API}/bank-reconciliation/{sid}/cleared", headers=h).json()}


def test_import_keeps_debits_only_when_asked_and_one_amount_column_is_signed(client, db):
    society, _flat, admin, manager, L = _books(client, db, "br9")
    h, sid = admin["headers"], str(society.id)
    csv_text = "Date,Description,Amount\n2025-01-09,IN,5000\n2025-01-10,OUT,-2000\n"
    r = _import(client, sid, manager["headers"], csv_text)
    assert [(x["direction"], x["amount"]) for x in r.json()] == [("credit", "5000.00")]      # as before
    r = _import(client, sid, manager["headers"], csv_text, include_debits="true")
    assert [(x["direction"], x["amount"]) for x in r.json()] == [("credit", "5000.00"), ("debit", "2000.00")]
    assert _import(client, sid, h, "Date,Description\n2025-01-09,IN\n").status_code == 422
    other = _import(client, sid, h, csv_text, bank_account_id=L["audit_fees"]["id"])      # an expense ledger
    assert other.status_code == 422


def test_a_debit_row_is_never_a_residents_payment(client, db):
    society, _flat, admin, manager, L = _books(client, db, "br10")
    h, sid = admin["headers"], str(society.id)
    rows = _import(client, sid, manager["headers"], "Date,Description,Amount\n2025-01-10,OUT,-2000\n",
                   include_debits="true").json()
    r = client.get(f"{BILLING}/bank-reconciliation/{rows[0]['id']}/candidates", headers=manager["headers"])
    assert r.status_code == 200 and r.json() == []


def test_an_online_payment_confirmed_on_the_billing_screen_is_cleared_in_the_books(client, db):
    society, flat, admin, manager, L = _books(client, db, "br11")
    h, sid = admin["headers"], str(society.id)
    paid_on = date.today().isoformat()
    r = client.post(f"{BILLING}/online-payments", headers=manager["headers"], data={
        "flat_id": str(flat.id), "amount": "5500.00", "payment_date": paid_on, "payment_mode": "upi",
        "transaction_ref": "UTR999"}, files={"screenshot": ("u.jpg", io.BytesIO(b"\xff\xd8\xff\xe0x"), "image/jpeg")})
    assert r.status_code == 201, r.text
    sub = r.json()
    brs = _brs(client, h, sid, paid_on)
    assert [x["amount"] for x in brs["deposits_not_cleared"]] == ["5500.00"]

    row = _import(client, sid, manager["headers"],
                  f"Date,Description,Reference,Amount\n{paid_on},UPI CR,UTR999,5500.00\n").json()[0]
    r = client.post(f"{BILLING}/bank-reconciliation/{row['id']}/confirm", json={"submission_id": sub["id"]},
                    headers=manager["headers"])
    assert r.status_code == 200, r.text
    brs = _brs(client, h, sid, paid_on)
    assert brs["deposits_not_cleared"] == [] and brs["balance_per_bank"] == brs["balance_per_books"]


def test_clearing_the_line_in_the_books_reconciles_the_residents_payment(client, db):
    society, flat, admin, manager, L = _books(client, db, "br12")
    h, sid = admin["headers"], str(society.id)
    paid_on = date.today().isoformat()
    r = client.post(f"{BILLING}/online-payments", headers=manager["headers"], data={
        "flat_id": str(flat.id), "amount": "800.00", "payment_date": paid_on, "payment_mode": "upi",
        "transaction_ref": "UTR1"}, files={"screenshot": ("u.jpg", io.BytesIO(b"\xff\xd8\xff\xe0x"), "image/jpeg")})
    sub = r.json()
    assert sub["status"] == "pending"
    entry = _brs(client, h, sid, paid_on)["deposits_not_cleared"][0]["entry_id"]
    _clear(client, h, sid, [entry], paid_on)
    got = client.get(f"{BILLING}/online-payments/{sub['id']}", headers=manager["headers"]).json()
    assert got["status"] == "reconciled"


def test_a_voucher_cancelled_after_matching_frees_its_statement_row(client, db):
    society, _flat, admin, _m, L = _books(client, db, "br13")
    h, sid = admin["headers"], str(society.id)
    chq = _cheque(client, h, sid, L, 2000, "2025-01-06", ref="000123")
    row = _import(client, sid, h, "Date,Description,Reference,Debit,Credit\n2025-01-09,CHQ,000123,2000.00,\n",
                  bank_account_id=L["bank"]["id"]).json()[0]
    entry = _entry_id(_brs(client, h, sid, "2025-01-31"), chq["voucher_number"])
    r = client.post(f"{API}/bank-reconciliation/{sid}/rows/{row['id']}/match", json={"entry_id": entry}, headers=h)
    assert r.status_code == 200, r.text
    assert client.post(f"{API}/vouchers/{chq['id']}/cancel", json={"reason": "Stopped the cheque"},
                       headers=h).status_code == 200
    again = client.get(f"{BILLING}/bank-reconciliation/society/{sid}", params={"match_status": "unmatched"},
                       headers=h).json()
    assert [x["id"] for x in again] == [row["id"]]


def test_a_residents_payment_goes_into_the_bank_ledger_chosen(client, db):
    society, flat, admin, manager, L = _books(client, db, "br14")
    h, sid = admin["headers"], str(society.id)
    other = client.post(f"{API}/ledgers", headers=h, json={
        "society_id": sid, "group_id": L["bank"]["group_id"], "name": "Savings Account", "is_bank": True}).json()
    paid_on = date.today().isoformat()
    form = {"flat_id": str(flat.id), "amount": "800.00", "payment_date": paid_on, "payment_mode": "upi",
            "transaction_ref": "UTR5"}
    shot = {"screenshot": ("u.jpg", io.BytesIO(b"\xff\xd8\xff\xe0x"), "image/jpeg")}
    bad = client.post(f"{BILLING}/online-payments", headers=manager["headers"], files=shot,
                      data={**form, "deposit_account_id": L["cash"]["id"]})
    assert bad.status_code == 422 and "bank" in bad.json()["detail"].lower()
    ok = client.post(f"{BILLING}/online-payments", headers=manager["headers"], files=shot,
                     data={**form, "deposit_account_id": other["id"]})
    assert ok.status_code == 201, ok.text
    assert ok.json()["deposit_account_name"] == "Savings Account"
    assert [x["amount"] for x in _brs(client, h, sid, paid_on, other["id"])["deposits_not_cleared"]] == ["800.00"]
    assert _brs(client, h, sid, paid_on)["deposits_not_cleared"] == []            # the default bank saw nothing
