"""Every report must read the books the same way: only approved, live vouchers count. A payment waiting for approval
(or one that was rejected) is not in the books yet, so it must not show up in the Receipts & Payments, the Schedule of
Funds, the dashboard figures or the spend per maintenance element — and a closed year's closing entry, which zeroes
every income and expense ledger, must not erase that year's spend from the element report."""
from datetime import date
from decimal import Decimal

from tests.accounts.test_reports import API, _books, _report, _voucher

today = date.today()


def _pending_payment(client, h, sid, L, expense, amount, on, paid_from="bank"):
    """A payment entered by the admin, left waiting for approval."""
    r = client.post(f"{API}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": on,
        "entries": [{"account_id": L[expense]["id"], "debit": str(amount)},
                    {"account_id": L[paid_from]["id"], "credit": str(amount)}]})
    assert r.status_code == 201, r.text
    assert r.json()["approval_status"] == "pending"
    return r.json()


def test_receipts_and_payments_still_balance_with_a_payment_waiting_for_approval(client, db):
    society, _flat, admin, *_, L = _books(client, db, "bi1")
    h, sid = admin["headers"], str(society.id)
    before = _report(client, h, sid, "receipts-payments", "2024-25")
    assert before["balanced"]
    v = _pending_payment(client, h, sid, L, "audit_fees", 5000, "2025-02-01")
    waiting = _report(client, h, sid, "receipts-payments", "2024-25")
    assert waiting["balanced"] and waiting["sides"] == before["sides"]      # not in the books yet
    assert client.post(f"{API}/vouchers/{v['id']}/approve", json={}, headers=h).status_code == 200
    after = _report(client, h, sid, "receipts-payments", "2024-25")
    assert after["balanced"] and after["sides"] != before["sides"]


def test_a_rejected_payment_is_never_in_the_receipts_and_payments(client, db):
    society, _flat, admin, *_, L = _books(client, db, "bi2")
    h, sid = admin["headers"], str(society.id)
    before = _report(client, h, sid, "receipts-payments", "2024-25")
    v = _pending_payment(client, h, sid, L, "audit_fees", 5000, "2025-02-01")
    assert client.post(f"{API}/vouchers/{v['id']}/reject", json={"reason": "Not authorised"},
                       headers=h).status_code == 200
    rejected = _report(client, h, sid, "receipts-payments", "2024-25")
    assert rejected["balanced"] and rejected["sides"] == before["sides"]


def test_schedule_of_funds_leaves_out_a_payment_waiting_for_approval(client, db):
    society, _flat, admin, *_, L = _books(client, db, "bi3")
    h, sid = admin["headers"], str(society.id)

    def utilised():
        funds = _report(client, h, sid, "funds", "2024-25")
        return next(r for r in funds["rows"] if r["label"] == "Sinking Fund")["cells"][2]

    assert utilised() == ""
    v = _pending_payment(client, h, sid, L, "sinking_fund", 1000, "2025-02-01")
    assert utilised() == ""
    assert client.post(f"{API}/vouchers/{v['id']}/approve", json={}, headers=h).status_code == 200
    assert utilised() == "1000.00"


def test_dashboard_year_figures_wait_for_approval(client, db):
    society, _flat, admin, *_, L = _books(client, db, "bi4")
    h, sid = admin["headers"], str(society.id)
    base = Decimal(client.get(f"{API}/summary/{sid}", headers=h).json()["fy_expense"])
    v = _pending_payment(client, h, sid, L, "audit_fees", 700, str(today))
    assert Decimal(client.get(f"{API}/summary/{sid}", headers=h).json()["fy_expense"]) == base
    assert client.post(f"{API}/vouchers/{v['id']}/approve", json={}, headers=h).status_code == 200
    assert Decimal(client.get(f"{API}/summary/{sid}", headers=h).json()["fy_expense"]) == base + 700


def test_spend_per_element_counts_approved_vouchers_only_and_survives_year_closing(client, db):
    society, _flat, admin, *_, L = _books(client, db, "bi5")
    h, sid = admin["headers"], str(society.id)
    span = {"date_from": "2024-04-01", "date_to": "2025-03-31"}

    def spent():
        r = client.get(f"{API}/expenses-by-element/{sid}", params=span, headers=h)
        assert r.status_code == 200, r.text
        rows = {x["name"]: Decimal(x["amount"]) for x in r.json()["unlinked"]}
        for e in r.json()["elements"]:
            rows.update({x["name"]: Decimal(x["amount"]) for x in e["ledgers"]})
        return rows

    assert spent()["Electricity Charges (Common Areas)"] == 30000
    v = _pending_payment(client, h, sid, L, "electricity", 999, "2025-02-01")
    assert spent()["Electricity Charges (Common Areas)"] == 30000           # waiting for approval: not spent yet
    client.post(f"{API}/vouchers/{v['id']}/reject", json={"reason": "No"}, headers=h)
    assert spent()["Electricity Charges (Common Areas)"] == 30000

    assert client.post(f"{API}/years/{sid}/2024-25/close", json={"reserve_pct": "25"}, headers=h).status_code == 200
    assert spent()["Electricity Charges (Common Areas)"] == 30000           # the closing entry is not a refund
