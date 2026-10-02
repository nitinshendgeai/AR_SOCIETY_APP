"""Society accounts: the standard chart, vouchers entered by the society,
the automatic postings from bills, payments and vendor bills, and the
ledgers built from them."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import MaintenanceBill
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig
from tests.conftest import make_user

API = "/api/v1/accounts"


def _chart(client, h, sid):
    r = client.get(f"{API}/chart/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _ledgers(client, h, sid):
    """{system_key or name: ledger}"""
    r = client.get(f"{API}/ledgers/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _balance(client, h, sid, key):
    for group in _chart(client, h, sid):
        for a in group["accounts"]:
            if a["system_key"] == key:
                return Decimal(a["balance"])
    raise AssertionError(key)


def _issued_bills(client, db, tag):
    """Two flats billed ₹2,500 service charges + ₹500 sinking fund + ₹300
    water with 18% GST, and issued."""
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    h = manager["headers"]
    _charge(client, h, society.id, name="Service Charges", amount="2500.00")
    _charge(client, h, society.id, name="Sinking Fund", amount="500.00", charge_type="sinking_fund")
    _charge(client, h, society.id, name="Water", amount="300.00", tax="18", charge_type="water")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    bill1 = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    return society, flat1, flat2, manager, resident, bill1


# ── Chart of accounts ─────────────────────────────────────────────────────────

def test_standard_chart_is_created_on_first_visit(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc1")
    groups = _chart(client, manager["headers"], society.id)
    names = [g["name"] for g in groups]
    assert names[:3] == ["Share Capital", "Reserve Fund & Other Funds", "Income & Expenditure Account"]
    assert "Cash & Bank Balances" in names and "Income from Members" in names
    ledgers = _ledgers(client, manager["headers"], society.id)
    for key in ("sinking_fund", "repair_fund", "members_dues", "cash", "bank", "service_charges",
                "interest_on_arrears", "sundry_creditors", "security_charges", "audit_fees"):
        assert key in ledgers
    assert ledgers["bank"]["is_default_bank"] and ledgers["cash"]["is_cash"]
    # Visiting again doesn't duplicate anything
    assert len(_ledgers(client, manager["headers"], society.id)) == len(ledgers)


def test_bank_ledger_named_from_bill_bank_details(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc2")
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={
        "bank_name": "Union Bank of India", "bank_account_number": "520101234567890", "bank_ifsc": "UBIN0530000",
    }, headers=manager["headers"])
    assert r.status_code == 200, r.text
    bank = _ledgers(client, manager["headers"], society.id)["bank"]
    assert bank["name"] == "Union Bank of India A/c 7890"
    assert bank["bank_ifsc"] == "UBIN0530000"


def test_add_ledger_with_opening_balance_and_default_bank(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc3")
    h, sid = manager["headers"], str(society.id)
    cash_bank = next(g for g in _chart(client, h, sid) if g["system_key"] == "cash_bank")
    r = client.post(f"{API}/ledgers", json={
        "society_id": sid, "group_id": cash_bank["id"], "name": "HDFC Bank Current A/c",
        "is_bank": True, "is_default_bank": True, "opening_balance": "125000.50",
    }, headers=h)
    assert r.status_code == 201, r.text
    hdfc = r.json()
    assert hdfc["opening_type"] == "dr" and hdfc["is_default_bank"]
    ledgers = _ledgers(client, h, sid)
    assert not ledgers["bank"]["is_default_bank"]
    assert Decimal(next(a for g in _chart(client, h, sid) for a in g["accounts"]
                        if a["id"] == hdfc["id"])["balance"]) == Decimal("125000.50")

    # Names are unique; standard ledgers can't be deactivated
    r = client.post(f"{API}/ledgers", json={"society_id": sid, "group_id": cash_bank["id"],
                                            "name": "hdfc bank current a/c"}, headers=h)
    assert r.status_code == 409
    r = client.patch(f"{API}/ledgers/{ledgers['cash']['id']}", json={"is_active": False}, headers=h)
    assert r.status_code == 409
    r = client.patch(f"{API}/ledgers/{hdfc['id']}", json={"name": "HDFC Bank A/c 1122"}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "HDFC Bank A/c 1122"


# ── Vouchers ──────────────────────────────────────────────────────────────────

def test_payment_voucher_posts_and_numbers_by_financial_year(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc4")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    r = client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": "2026-09-15",
        "narration": "MSEDCL bill for Aug-2026", "reference": "CHQ 000123",
        "entries": [{"account_id": L["electricity"]["id"], "debit": "8450"},
                    {"account_id": L["bank"]["id"], "credit": "8450"}],
    }, headers=h)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["voucher_number"] == "PV/2026-27/0001" and v["fiscal_year"] == "2026-27"
    assert v["amount"] == "8450.00" and not v["is_auto"]
    r = client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": "2026-10-01",
        "entries": [{"account_id": L["audit_fees"]["id"], "debit": "5000"},
                    {"account_id": L["cash"]["id"], "credit": "5000"}],
    }, headers=h)
    assert r.json()["voucher_number"] == "PV/2026-27/0002"
    r = client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": "2027-04-02",
        "entries": [{"account_id": L["audit_fees"]["id"], "debit": "100"},
                    {"account_id": L["cash"]["id"], "credit": "100"}],
    }, headers=h)
    assert r.json()["voucher_number"] == "PV/2027-28/0001"

    assert _balance(client, h, sid, "electricity") == Decimal("8450")
    assert _balance(client, h, sid, "bank") == Decimal("-8450")
    day_book = client.get(f"{API}/vouchers/society/{sid}", headers=h).json()
    assert [x["voucher_number"] for x in day_book][0] == "PV/2027-28/0001"


def test_voucher_rules(client, db):
    society, flat1, _flat2, manager, _res, _other = _rig(db, "acc5")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)

    def post(vtype, entries):
        return client.post(f"{API}/vouchers", json={
            "society_id": sid, "voucher_type": vtype, "voucher_date": "2026-09-20", "entries": entries,
        }, headers=h)

    # Unbalanced
    assert post("journal", [{"account_id": L["depreciation"]["id"], "debit": "100"},
                            {"account_id": L["plant_machinery"]["id"], "credit": "90"}]).status_code == 422
    # A line with both sides
    assert post("journal", [{"account_id": L["depreciation"]["id"], "debit": "100", "credit": "100"},
                            {"account_id": L["plant_machinery"]["id"], "credit": "100"}]).status_code == 422
    # Journal can't touch cash/bank; contra only cash/bank; receipt debits cash/bank
    assert post("journal", [{"account_id": L["audit_fees"]["id"], "debit": "100"},
                            {"account_id": L["cash"]["id"], "credit": "100"}]).status_code == 422
    assert post("contra", [{"account_id": L["bank"]["id"], "debit": "100"},
                           {"account_id": L["misc_income"]["id"], "credit": "100"}]).status_code == 422
    assert post("receipt", [{"account_id": L["misc_income"]["id"], "debit": "100"},
                            {"account_id": L["cash"]["id"], "credit": "100"}]).status_code == 422
    # Members' Dues lines name the flat
    assert post("receipt", [{"account_id": L["cash"]["id"], "debit": "100"},
                            {"account_id": L["members_dues"]["id"], "credit": "100"}]).status_code == 422
    assert post("receipt", [{"account_id": L["cash"]["id"], "debit": "100"},
                            {"account_id": L["members_dues"]["id"], "credit": "100",
                             "flat_id": str(flat1.id)}]).status_code == 201
    # Contra: cash deposited in the bank
    r = post("contra", [{"account_id": L["bank"]["id"], "debit": "100"},
                        {"account_id": L["cash"]["id"], "credit": "100"}])
    assert r.status_code == 201 and r.json()["voucher_number"].startswith("CV/")
    assert _balance(client, h, sid, "cash") == 0 and _balance(client, h, sid, "bank") == 100


def test_cancelled_voucher_drops_out_of_the_books(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc6")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    v = client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": "journal", "voucher_date": "2026-09-20",
        "entries": [{"account_id": L["depreciation"]["id"], "debit": "700"},
                    {"account_id": L["plant_machinery"]["id"], "credit": "700"}],
    }, headers=h).json()
    assert _balance(client, h, sid, "depreciation") == 700
    r = client.post(f"{API}/vouchers/{v['id']}/cancel", json={"reason": "Wrong amount"}, headers=h)
    assert r.status_code == 200 and r.json()["is_cancelled"]
    assert _balance(client, h, sid, "depreciation") == 0
    assert client.post(f"{API}/vouchers/{v['id']}/cancel", json={"reason": "again"}, headers=h).status_code == 409


# ── Automatic postings ────────────────────────────────────────────────────────

def test_issued_bill_posts_member_bill_by_charge_head(client, db):
    society, flat1, flat2, manager, _res, bill1 = _issued_bills(client, db, "acc7")
    h, sid = manager["headers"], str(society.id)
    v = db.query(Voucher).filter_by(source_type="maintenance_bill", source_id=bill1.id).one()
    assert v.voucher_type == "bill" and v.reference == bill1.invoice_number
    assert v.voucher_number.startswith("BV/")
    # 2 flats × (2500 service + 500 sinking + 300 water + 54 GST)
    assert _balance(client, h, sid, "members_dues") == Decimal("6708")
    assert _balance(client, h, sid, "service_charges") == Decimal("-5000")
    assert _balance(client, h, sid, "sinking_fund") == Decimal("-1000")
    assert _balance(client, h, sid, "water_recovered") == Decimal("-600")
    assert _balance(client, h, sid, "gst_payable") == Decimal("-108")

    members = client.get(f"{API}/members/{sid}", headers=h).json()
    row = next(m for m in members["members"] if m["flat_id"] == str(flat1.id))
    assert row["balance_dr_cr"] == {"amount": "3354.00", "type": "Dr"} and row["member_name"] == "Asha Rao"


def test_payment_posts_receipt_and_member_ledger(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "acc8")
    h, sid = manager["headers"], str(society.id)
    r = client.post("/api/v1/billing/payments", json={
        "bill_id": str(bill1.id), "amount": "3000.00", "payment_date": str(date.today()),
        "payment_mode": "cheque", "cheque_number": "004512", "bank_name": "UBI",
    }, headers=h)
    assert r.status_code == 201, r.text
    # Cash on account, from the Record Payment form
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": str(flat1.id), "amount": "354.00", "payment_date": str(date.today()), "payment_mode": "cash",
    }, headers=h)
    assert r.status_code == 201, r.text

    assert _balance(client, h, sid, "bank") == Decimal("3000")
    assert _balance(client, h, sid, "cash") == Decimal("354")
    dues = _ledgers(client, h, sid)["members_dues"]
    st = client.get(f"{API}/ledgers/{dues['id']}/statement", params={"flat_id": str(flat1.id)}, headers=h).json()
    assert [l["voucher_type"] for l in st["lines"]] == ["bill", "receipt", "receipt"]
    assert st["closing_dr_cr"] == {"amount": "0.00", "type": "Dr"}
    assert "Cheque No. 004512" in st["lines"][1]["narration"]
    assert st["lines"][1]["particulars"] == "Bank Account"


def test_cancelled_bill_and_rejected_payment_are_struck_out(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "acc9")
    h, sid = manager["headers"], str(society.id)
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": str(flat1.id), "amount": "500.00", "payment_date": str(date.today()),
        "payment_mode": "cheque", "transaction_ref": "000777",
    }, headers=h)
    sub_id = r.json()["id"]
    assert _balance(client, h, sid, "bank") == 500
    r = client.patch(f"/api/v1/billing/online-payments/{sub_id}/status",
                     json={"status": "rejected", "review_notes": "Not in bank statement"}, headers=h)
    assert r.status_code == 200, r.text
    assert _balance(client, h, sid, "bank") == 0

    assert client.post(f"/api/v1/billing/bills/{bill1.id}/cancel", json={"reason": "Duplicate"},
                       headers=h).status_code == 200
    assert _balance(client, h, sid, "members_dues") == Decimal("3354")
    v = db.query(Voucher).filter_by(source_type="maintenance_bill", source_id=bill1.id).one()
    assert v.is_cancelled and "Duplicate" in v.cancel_reason
    # Auto-posted vouchers are cancelled from their source, not directly
    v2 = db.query(Voucher).filter(Voucher.source_type == "maintenance_bill", Voucher.is_cancelled == False).first()
    assert client.post(f"{API}/vouchers/{v2.id}/cancel", json={"reason": "Not needed"}, headers=h).status_code == 409


def test_vendor_bill_and_payment_post_purchase_and_payment(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc10")
    h, sid = manager["headers"], str(society.id)
    admin = make_user(db, "admin@acc10.com", role="Society Admin")
    vendor_id = client.post("/api/v1/vendors/", json={
        "society_id": sid, "company_name": "Shield Security", "mobile": "9876543210", "category": "security",
    }, headers=admin["headers"]).json()["id"]
    inv = client.post("/api/v1/vendors/invoices", json={
        "society_id": sid, "vendor_id": vendor_id, "invoice_number": "SS/112", "invoice_date": "2026-09-05",
        "amount": "40000", "gst_amount": "7200", "total_amount": "47200",
    }, headers=h).json()
    assert _balance(client, h, sid, "security_charges") == Decimal("47200")
    assert _balance(client, h, sid, "sundry_creditors") == Decimal("-47200")

    r = client.post(f"/api/v1/vendors/invoices/{inv['id']}/payments", json={
        "amount": "20000", "paid_date": "2026-09-10", "payment_mode": "neft", "payment_ref": "UTR9",
    }, headers=h)
    assert r.status_code == 200, r.text
    assert _balance(client, h, sid, "sundry_creditors") == Decimal("-27200")
    assert _balance(client, h, sid, "bank") == Decimal("-20000")

    creditors = _ledgers(client, h, sid)["sundry_creditors"]
    st = client.get(f"{API}/ledgers/{creditors['id']}/statement", params={"vendor_id": vendor_id},
                    headers=h).json()
    assert st["closing_dr_cr"] == {"amount": "27200.00", "type": "Cr"}

    # A bill booked to a chosen expense head
    L = _ledgers(client, h, sid)
    client.post("/api/v1/vendors/invoices", json={
        "society_id": sid, "vendor_id": vendor_id, "invoice_number": "SS/113", "invoice_date": "2026-09-06",
        "amount": "1500", "total_amount": "1500", "expense_account_id": L["cctv_maintenance"]["id"],
    }, headers=h)
    assert _balance(client, h, sid, "cctv_maintenance") == Decimal("1500")


def test_sync_posts_what_existed_before_the_books(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "acc11")
    h, sid = manager["headers"], str(society.id)
    client.post("/api/v1/billing/payments", json={
        "bill_id": str(bill1.id), "amount": "1000.00", "payment_date": str(date.today()), "payment_mode": "cash",
    }, headers=h)
    # As if these were recorded before the accounts module existed
    for v in db.query(Voucher).filter(Voucher.society_id == society.id):
        db.delete(v)
    db.commit()

    summary = client.get(f"{API}/summary/{sid}", headers=h).json()
    assert summary["pending_postings"] == 3
    r = client.post(f"{API}/sync/{sid}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["bills"] == 2 and r.json()["receipts"] == 1
    assert client.post(f"{API}/sync/{sid}", headers=h).json()["total"] == 0
    summary = client.get(f"{API}/summary/{sid}", headers=h).json()
    assert summary["pending_postings"] == 0
    assert summary["cash"] == "1000.00" and summary["members_dues"] == "5708.00"
    assert Decimal(summary["fy_income"]) == Decimal("5600")  # service + water; sinking fund isn't income


def test_statement_period_carries_opening_balance(client, db):
    society, *_, manager, _res, _other = _rig(db, "acc12")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    for d, amt in (("2026-08-10", "1000"), ("2026-09-10", "250")):
        client.post(f"{API}/vouchers", json={
            "society_id": sid, "voucher_type": "receipt", "voucher_date": d,
            "entries": [{"account_id": L["cash"]["id"], "debit": amt},
                        {"account_id": L["misc_income"]["id"], "credit": amt}],
        }, headers=h)
    st = client.get(f"{API}/ledgers/{L['cash']['id']}/statement",
                    params={"date_from": "2026-09-01", "date_to": "2026-09-30"}, headers=h).json()
    assert st["opening"] == "1000.00" and len(st["lines"]) == 1
    assert st["lines"][0]["particulars"] == "Miscellaneous Income"
    assert st["closing_dr_cr"] == {"amount": "1250.00", "type": "Dr"}


def test_residents_cannot_see_the_books(client, db):
    society, *_, manager, resident, _other = _rig(db, "acc13")
    sid = str(society.id)
    assert client.get(f"{API}/chart/{sid}", headers=resident["headers"]).status_code == 403
    assert client.get(f"{API}/summary/{sid}", headers=resident["headers"]).status_code == 403
    assert client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": "journal", "voucher_date": "2026-09-01", "entries": [],
    }, headers=resident["headers"]).status_code == 403
