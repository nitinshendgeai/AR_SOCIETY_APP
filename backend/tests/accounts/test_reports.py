"""Financial statements and year-end closing: Trial Balance, Income &
Expenditure, Balance Sheet, Receipts & Payments and the Schedule of Funds
tally; closing a year transfers the result and locks the year; postings of
a closed year are shifted or reversed into the open year."""
from decimal import Decimal

from app.modules.accounts.models.accounts import Voucher
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

API = "/api/v1/accounts"


def _ledgers(client, h, sid):
    r = client.get(f"{API}/ledgers/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _voucher(client, h, sid, vtype, d, entries, expect=201, approver=None):
    r = client.post(f"{API}/vouchers", json={"society_id": sid, "voucher_type": vtype, "voucher_date": d,
                                              "entries": entries}, headers=h)
    assert r.status_code == expect, r.text
    v = r.json()
    if expect == 201 and v.get("approval_status") == "pending":
        # Payments and journals count in the books only once approved (these tests act as the society admin).
        ok = client.post(f"{API}/vouchers/{v['id']}/approve", json={"note": "Approved"},
                         headers=approver["headers"] if approver else h)
        assert ok.status_code == 200, ok.text
    return v


def _report(client, h, sid, report, fy):
    r = client.get(f"{API}/reports/{sid}/{report}", params={"fy": fy}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _amount(rows_or_sections, label, col=0):
    for s in rows_or_sections:
        for r in s["rows"]:
            if r["label"] == label:
                return Decimal(r["amounts"][col] or 0)
    raise AssertionError(label)


def _books(client, db, tag):
    """Opening balances on 1 Apr 2024 and a year of entries in FY 2024-25:
    bank ₹1,00,000, sinking fund ₹60,000, I&E account ₹40,000; service
    charges billed ₹50,000 to a flat, ₹45,000 of it received; SB interest
    ₹1,000; electricity paid ₹30,000. Surplus ₹21,000."""
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    admin = make_user(db, f"admin@{tag}.com", role="Society Admin")
    h, sid = admin["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    for key, amount in (("bank", "100000"), ("sinking_fund", "60000"), ("ie_surplus", "40000")):
        r = client.patch(f"{API}/ledgers/{L[key]['id']}", json={"opening_balance": amount}, headers=h)
        assert r.status_code == 200, r.text
    _voucher(client, h, sid, "journal", "2024-04-30", [
        {"account_id": L["members_dues"]["id"], "debit": "50000", "flat_id": str(flat1.id)},
        {"account_id": L["service_charges"]["id"], "credit": "50000"}])
    _voucher(client, h, sid, "receipt", "2024-06-15", [
        {"account_id": L["bank"]["id"], "debit": "45000"},
        {"account_id": L["members_dues"]["id"], "credit": "45000", "flat_id": str(flat1.id)}])
    _voucher(client, h, sid, "receipt", "2024-09-30", [
        {"account_id": L["bank"]["id"], "debit": "1000"},
        {"account_id": L["interest_sb"]["id"], "credit": "1000"}])
    _voucher(client, h, sid, "payment", "2025-01-10", [
        {"account_id": L["electricity"]["id"], "debit": "30000"},
        {"account_id": L["bank"]["id"], "credit": "30000"}])
    return society, flat1, admin, manager, resident, L


def test_trial_balance_tallies(client, db):
    society, _flat, admin, *_ , L = _books(client, db, "rp1")
    tb = _report(client, admin["headers"], str(society.id), "trial-balance", "2024-25")
    assert tb["kind"] == "table" and tb["balanced"]
    assert tb["heading"] == "Trial Balance as at 31st March 2025"
    assert tb["totals"] == ["151000.00", "151000.00"]   # bank 116000 + dues 5000 + electricity 30000
    cells = {r["label"]: r["cells"] for r in tb["rows"] if r["level"] == 1}
    assert cells[L["bank"]["name"]] == ["116000.00", ""]
    assert cells["Service Charges"] == ["", "50000.00"]


def test_income_expenditure_and_balance_sheet(client, db):
    society, _flat, admin, *_, L = _books(client, db, "rp2")
    h, sid = admin["headers"], str(society.id)
    ie = _report(client, h, sid, "income-expenditure", "2024-25")
    assert ie["heading"] == "Income & Expenditure Account for the year ended 31st March 2025"
    exp, inc = ie["sides"]
    assert _amount(exp["sections"], "Electricity Charges (Common Areas)") == 30000
    assert _amount(inc["sections"], "Service Charges") == 50000
    assert _amount(exp["sections"], "Excess of Income over Expenditure (Surplus) carried to Balance Sheet") == 21000
    assert exp["total"][0] == inc["total"][0] == "51000.00"
    assert ie["result"]["amounts"][0] == "21000.00"

    bs = _report(client, h, sid, "balance-sheet", "2024-25")
    assert bs["balanced"] and bs["heading"] == "Balance Sheet as at 31st March 2025"
    liab, assets = bs["sides"]
    assert _amount(liab["sections"], "Sinking Fund") == 60000
    assert _amount(liab["sections"], "Balance as per last Balance Sheet") == 40000
    assert _amount(liab["sections"], "Add: Surplus / (Less: Deficit) for the year") == 21000
    assert _amount(assets["sections"], L["members_dues"]["name"]) == 5000
    assert liab["total"][0] == assets["total"][0] == "121000.00"
    # Previous year column: the opening position
    assert liab["total"][1] == assets["total"][1] == "100000.00"


def test_receipts_payments_and_funds(client, db):
    society, _flat, admin, *_, L = _books(client, db, "rp3")
    h, sid = admin["headers"], str(society.id)
    rp = _report(client, h, sid, "receipts-payments", "2024-25")
    rec, pay = rp["sides"]
    assert rp["balanced"] and rec["total"] == pay["total"] == ["146000.00"]
    assert _amount(rec["sections"], L["bank"]["name"]) == 100000            # opening
    assert _amount(rec["sections"], "Received from members (maintenance & other charges)") == 45000
    assert _amount(pay["sections"], "Electricity Charges (Common Areas)") == 30000
    funds = _report(client, h, sid, "funds", "2024-25")
    row = next(r for r in funds["rows"] if r["label"] == "Sinking Fund")
    assert row["cells"] == ["60000.00", "", "", "60000.00"]

    for report in ("trial-balance", "income-expenditure", "balance-sheet", "receipts-payments", "funds"):
        r = client.get(f"{API}/reports/{sid}/{report}", params={"fy": "2024-25", "format": "pdf"}, headers=h)
        assert r.status_code == 200 and r.content[:4] == b"%PDF", report


def test_close_year_transfers_result_and_locks(client, db):
    society, flat, admin, manager, _res, L = _books(client, db, "rp4")
    h, sid = admin["headers"], str(society.id)
    years = {y["fy"]: y for y in client.get(f"{API}/years/{sid}", headers=h).json()}
    assert years["2024-25"]["can_close"] and years["2024-25"]["surplus"] == "21000.00"
    assert years["2024-25"]["suggested_reserve_pct"] == "25"
    assert not years["2025-26"]["is_closed"]

    # Managers keep the books but the committee closes them
    assert client.post(f"{API}/years/{sid}/2024-25/close", json={"reserve_pct": "25"},
                       headers=manager["headers"]).status_code == 403
    r = client.post(f"{API}/years/{sid}/2024-25/close", json={"reserve_pct": "25"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["surplus"] == "21000.00" and r.json()["reserve_transfer"] == "5250.00"
    closing = db.query(Voucher).filter_by(voucher_type="closing").one()
    assert closing.voucher_number == "YC/2024-25/0001" and str(closing.voucher_date) == "2025-03-31"

    # The year's statements read the same after closing
    ie = _report(client, h, sid, "income-expenditure", "2024-25")
    assert ie["result"]["amounts"][0] == "21000.00"
    tb = _report(client, h, sid, "trial-balance", "2024-25")
    assert tb["balanced"] and tb["totals"][0] == "151000.00"
    bs = _report(client, h, sid, "balance-sheet", "2024-25")
    liab, assets = bs["sides"]
    assert bs["balanced"] and liab["total"][0] == "121000.00"
    assert _amount(liab["sections"], "Less: Transferred to Reserve Fund") == -5250
    assert _amount(liab["sections"], "Reserve Fund") == 5250

    # Next year starts from the closed figures
    bs2 = _report(client, h, sid, "balance-sheet", "2025-26")
    assert _amount(bs2["sides"][0]["sections"], "Balance as per last Balance Sheet") == 55750
    assert bs2["balanced"]

    # The year is locked
    _voucher(client, h, sid, "payment", "2025-02-01", [
        {"account_id": L["audit_fees"]["id"], "debit": "100"},
        {"account_id": L["bank"]["id"], "credit": "100"}], expect=409)
    v = db.query(Voucher).filter_by(voucher_type="payment").first()
    assert client.post(f"{API}/vouchers/{v.id}/cancel", json={"reason": "Wrong entry"},
                       headers=h).status_code == 409
    assert client.patch(f"{API}/ledgers/{L['bank']['id']}", json={"opening_balance": "1"},
                        headers=h).status_code == 409
    assert client.post(f"{API}/years/{sid}/2024-25/close", json={}, headers=h).status_code == 409
    years = {y["fy"]: y for y in client.get(f"{API}/years/{sid}", headers=h).json()}
    assert years["2024-25"]["is_closed"] and years["2024-25"]["can_reopen"]
    assert years["2024-25"]["reserve_transfer"] == "5250.00"


def test_years_close_in_order_and_reopen_latest_first(client, db):
    society, _flat, admin, *_, L = _books(client, db, "rp5")
    h, sid = admin["headers"], str(society.id)
    _voucher(client, h, sid, "payment", "2025-05-05", [
        {"account_id": L["audit_fees"]["id"], "debit": "2000"},
        {"account_id": L["bank"]["id"], "credit": "2000"}])
    r = client.post(f"{API}/years/{sid}/2025-26/close", json={}, headers=h)
    assert r.status_code == 409 and "2024-25" in r.text
    assert client.post(f"{API}/years/{sid}/2024-25/close", json={"reserve_pct": "0"}, headers=h).status_code == 200
    r = client.post(f"{API}/years/{sid}/2025-26/close", json={}, headers=h)
    assert r.status_code == 200 and r.json()["surplus"] == "-2000.00" and r.json()["reserve_transfer"] == "0.00"

    from app.modules.accounts.services.accounts_service import fiscal_year
    from datetime import date
    current = fiscal_year(date.today())
    r = client.post(f"{API}/years/{sid}/{current}/close", json={}, headers=h)
    assert r.status_code == 409 and "isn't over" in r.text

    assert client.post(f"{API}/years/{sid}/2024-25/reopen", json={"reason": "Audit change"},
                       headers=h).status_code == 409
    assert client.post(f"{API}/years/{sid}/2025-26/reopen", json={"reason": "Audit change"},
                       headers=h).status_code == 200
    assert client.post(f"{API}/years/{sid}/2024-25/reopen", json={"reason": "Audit change"},
                       headers=h).status_code == 200
    assert db.query(Voucher).filter_by(voucher_type="closing", is_cancelled=False).count() == 0
    # Reopened: entries allowed again, and the income ledgers are back
    _voucher(client, h, sid, "payment", "2025-02-01", [
        {"account_id": L["audit_fees"]["id"], "debit": "100"},
        {"account_id": L["bank"]["id"], "credit": "100"}])
    ie = _report(client, h, sid, "income-expenditure", "2024-25")
    assert ie["result"]["amounts"][0] == "20900.00"


def test_closed_year_postings_shift_and_reverse(client, db):
    society, flat, admin, manager, _res, L = _books(client, db, "rp6")
    h, sid = admin["headers"], str(society.id)
    # Cash received in March 2025, posted in FY 2024-25
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": str(flat.id), "amount": "2000.00", "payment_date": "2025-03-10", "payment_mode": "cheque",
        "transaction_ref": "000881"}, headers=manager["headers"])
    assert r.status_code == 201, r.text
    sub_id = r.json()["id"]
    assert client.post(f"{API}/years/{sid}/2024-25/close", json={"reserve_pct": "25"}, headers=h).status_code == 200
    surplus = _report(client, h, sid, "income-expenditure", "2024-25")["result"]["amounts"][0]

    # A payment dated in the closed year is posted on 1 April 2025
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": str(flat.id), "amount": "500.00", "payment_date": "2025-03-20", "payment_mode": "cash"},
        headers=manager["headers"])
    assert r.status_code == 201, r.text
    late = db.query(Voucher).filter_by(source_type="online_payment", reference=r.json()["receipt_number"]).one()
    assert str(late.voucher_date) == "2025-04-01" and "FY 2024-25 books closed" in late.narration

    # The cheque of the closed year bounces: reversed in the open year
    r = client.patch(f"/api/v1/billing/online-payments/{sub_id}/status",
                     json={"status": "rejected", "review_notes": "Cheque returned"}, headers=manager["headers"])
    assert r.status_code == 200, r.text
    original = db.query(Voucher).filter(Voucher.source_type == "online_payment",
                                        Voucher.reference != late.reference).one()
    assert not original.is_cancelled and original.reversed_at is not None
    reversal = db.query(Voucher).filter_by(reversal_of_id=original.id).one()
    assert reversal.voucher_date >= late.voucher_date and "Cheque returned" in reversal.narration
    # The closed year is untouched; nothing left to post
    assert _report(client, h, sid, "income-expenditure", "2024-25")["result"]["amounts"][0] == surplus
    assert client.get(f"{API}/summary/{sid}", headers=h).json()["pending_postings"] == 0
    assert client.post(f"{API}/sync/{sid}", headers=h).json()["total"] == 0
    detail = client.get(f"{API}/vouchers/{original.id}", headers=h).json()
    assert detail["is_locked"] and detail["is_reversed"]


def test_income_ledgers_have_no_opening_balance(client, db):
    society, *_ , manager, _res, _other = _rig(db, "rp7")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    r = client.patch(f"{API}/ledgers/{L['service_charges']['id']}", json={"opening_balance": "500"}, headers=h)
    assert r.status_code == 422


def test_residents_cannot_see_statements(client, db):
    society, *_, manager, resident, _other = _rig(db, "rp8")
    sid = str(society.id)
    assert client.get(f"{API}/reports/{sid}/balance-sheet", headers=resident["headers"]).status_code == 403
    assert client.get(f"{API}/years/{sid}", headers=resident["headers"]).status_code == 403
    r = client.get(f"{API}/reports/{sid}/balance-sheet", headers=manager["headers"])
    assert r.status_code == 200 and r.json()["provisional"]
    assert client.get(f"{API}/reports/{sid}/nonsense", headers=manager["headers"]).status_code == 404
    assert client.get(f"{API}/reports/{sid}/funds", params={"fy": "2026"},
                      headers=manager["headers"]).status_code == 422
