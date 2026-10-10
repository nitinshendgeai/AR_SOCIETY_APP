"""Member AR ledger and billing reconciliation regression tests."""
from datetime import date

from app.modules.billing.models.billing import BillStatus, BillingCycle, MaintenanceBill, PaymentMode, PaymentReceipt
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

API = "/api/v1/accounts"


def _ledgers(client, headers, sid):
    r = client.get(f"{API}/ledgers/{sid}", headers=headers)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _voucher(client, headers, sid, entries, approver, d="2026-04-30", vtype="journal"):
    """A manual voucher. Journals and payments only count in the books once the committee/admin approves them."""
    r = client.post(
        f"{API}/vouchers",
        json={"society_id": sid, "voucher_type": vtype, "voucher_date": d, "entries": entries},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    v = r.json()
    if v["approval_status"] == "pending":
        ok = client.post(f"{API}/vouchers/{v['id']}/approve", json={"note": "Approved"}, headers=approver["headers"])
        assert ok.status_code == 200, ok.text
    return v


def test_member_ar_reconciles_to_billing_outstanding(client, db):
    society, flat, _flat2, manager, _resident, _other = _rig(db, "memberar1")
    sid = str(society.id)
    h = manager["headers"]
    ledgers = _ledgers(client, h, sid)
    approver = make_user(db, f"approver-{sid[:8]}@t.com", role="Society Admin")

    cycle = BillingCycle(
        society_id=society.id,
        name="April 2026 Maintenance",
        cycle_start=date(2026, 4, 1),
        cycle_end=date(2026, 4, 30),
        due_date=date(2026, 5, 10),
        total_flats_billed=1,
        total_amount_generated=1000,
    )
    db.add(cycle)
    db.flush()
    bill = MaintenanceBill(
        society_id=society.id,
        cycle_id=cycle.id,
        flat_id=flat.id,
        invoice_number="AR-TEST-0001",
        bill_status=BillStatus.PARTIALLY_PAID,
        bill_date=date(2026, 4, 1),
        due_date=date(2026, 5, 10),
        subtotal=1000,
        total_amount=1000,
        paid_amount=400,
        outstanding=600,
    )
    db.add(bill)
    db.commit()

    _voucher(client, h, sid, [
        {"account_id": ledgers["members_dues"]["id"], "debit": "1000", "flat_id": str(flat.id)},
        {"account_id": ledgers["service_charges"]["id"], "credit": "1000"},
    ], approver)
    _voucher(client, h, sid, [
        {"account_id": ledgers["bank"]["id"], "debit": "400"},
        {"account_id": ledgers["members_dues"]["id"], "credit": "400", "flat_id": str(flat.id)},
    ], approver, vtype="receipt")

    r = client.get(f"{API}/members/{sid}/ar-reconciliation", headers=h)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["members"] if x["flat_id"] == str(flat.id))
    assert row["closing_ar"] == "600.00"
    assert row["operational_outstanding"] == "600.00"
    assert row["reconciliation_difference"] == "0.00"
    assert row["reconciled"] is True


def test_member_ar_statement_exposes_bill_wise_and_voucher_lines(client, db):
    society, flat, _flat2, manager, _resident, _other = _rig(db, "memberar2")
    sid = str(society.id)
    h = manager["headers"]
    ledgers = _ledgers(client, h, sid)
    approver = make_user(db, f"approver-{sid[:8]}@t.com", role="Society Admin")

    cycle = BillingCycle(
        society_id=society.id,
        name="May 2026 Maintenance",
        cycle_start=date(2026, 5, 1),
        cycle_end=date(2026, 5, 31),
        due_date=date(2026, 6, 10),
        total_flats_billed=1,
        total_amount_generated=1500,
    )
    db.add(cycle)
    db.flush()
    db.add(MaintenanceBill(
        society_id=society.id,
        cycle_id=cycle.id,
        flat_id=flat.id,
        invoice_number="AR-TEST-0002",
        bill_status=BillStatus.ISSUED,
        bill_date=date(2026, 5, 1),
        due_date=date(2026, 6, 10),
        subtotal=1500,
        total_amount=1500,
        paid_amount=0,
        outstanding=1500,
    ))
    db.commit()

    _voucher(client, h, sid, [
        {"account_id": ledgers["members_dues"]["id"], "debit": "1500", "flat_id": str(flat.id)},
        {"account_id": ledgers["service_charges"]["id"], "credit": "1500"},
    ], approver)

    r = client.get(f"{API}/members/{sid}/{flat.id}/ar-statement", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["member_account_number"].startswith("10")
    assert data["closing_ar"] == "1500.00"
    assert data["operational_outstanding"] == "1500.00"
    assert len(data["lines"]) == 1
    assert data["lines"][0]["debit"] == "1500.00"
    assert data["bills"][0]["invoice_number"] == "AR-TEST-0002"


def test_member_ar_historical_snapshot_uses_dated_receipts(client, db):
    society, flat, _flat2, manager, _resident, _other = _rig(db, "memberar3")
    sid = str(society.id)
    h = manager["headers"]
    ledgers = _ledgers(client, h, sid)
    approver = make_user(db, f"approver-{sid[:8]}@t.com", role="Society Admin")

    cycle = BillingCycle(
        society_id=society.id,
        name="June 2026 Maintenance",
        cycle_start=date(2026, 6, 1),
        cycle_end=date(2026, 6, 30),
        due_date=date(2026, 7, 10),
        total_flats_billed=1,
        total_amount_generated=1000,
    )
    db.add(cycle)
    db.flush()
    bill = MaintenanceBill(
        society_id=society.id,
        cycle_id=cycle.id,
        flat_id=flat.id,
        invoice_number="AR-TEST-0003",
        bill_status=BillStatus.PARTIALLY_PAID,
        bill_date=date(2026, 6, 1),
        due_date=date(2026, 7, 10),
        subtotal=1000,
        total_amount=1000,
        paid_amount=400,
        outstanding=600,
    )
    db.add(bill)
    db.flush()

    _voucher(client, h, sid, [
        {"account_id": ledgers["members_dues"]["id"], "debit": "1000", "flat_id": str(flat.id)},
        {"account_id": ledgers["service_charges"]["id"], "credit": "1000"},
    ], approver, d="2026-06-01")
    _voucher(client, h, sid, [
        {"account_id": ledgers["bank"]["id"], "debit": "400"},
        {"account_id": ledgers["members_dues"]["id"], "credit": "400", "flat_id": str(flat.id)},
    ], approver, d="2026-06-20", vtype="receipt")
    db.add(PaymentReceipt(
        society_id=society.id,
        bill_id=bill.id,
        flat_id=flat.id,
        receipt_number="AR-RECEIPT-0003",
        payment_date=date(2026, 6, 20),
        amount=400,
        payment_mode=PaymentMode.CASH,
    ))
    db.commit()

    before_payment = client.get(
        f"{API}/members/{sid}/{flat.id}/ar-statement?date_to=2026-06-10",
        headers=h,
    )
    assert before_payment.status_code == 200, before_payment.text
    assert before_payment.json()["closing_ar"] == "1000.00"
    assert before_payment.json()["operational_outstanding"] == "1000.00"

    after_payment = client.get(
        f"{API}/members/{sid}/{flat.id}/ar-statement?date_to=2026-06-30",
        headers=h,
    )
    assert after_payment.status_code == 200, after_payment.text
    assert after_payment.json()["closing_ar"] == "600.00"
    assert after_payment.json()["operational_outstanding"] == "600.00"
    assert after_payment.json()["reconciled"] is True
