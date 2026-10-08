"""Member AR ledger and billing reconciliation regression tests."""
from decimal import Decimal

from app.modules.billing.models.billing import BillStatus, BillingCycle, MaintenanceBill
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

API = "/api/v1/accounts"


def _ledgers(client, headers, sid):
    r = client.get(f"{API}/ledgers/{sid}", headers=headers)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _voucher(client, headers, sid, entries, d="2026-04-30"):
    r = client.post(
        f"{API}/vouchers",
        json={"society_id": sid, "voucher_type": "journal", "voucher_date": d, "entries": entries},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_member_ar_reconciles_to_billing_outstanding(client, db):
    society, flat, _flat2, manager, _resident, _other = _rig(db, "memberar1")
    sid = str(society.id)
    h = manager["headers"]
    ledgers = _ledgers(client, h, sid)

    cycle = BillingCycle(
        society_id=society.id,
        name="April 2026 Maintenance",
        cycle_start="2026-04-01",
        cycle_end="2026-04-30",
        due_date="2026-05-10",
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
        bill_date="2026-04-01",
        due_date="2026-05-10",
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
    ])
    _voucher(client, h, sid, [
        {"account_id": ledgers["bank"]["id"], "debit": "400"},
        {"account_id": ledgers["members_dues"]["id"], "credit": "400", "flat_id": str(flat.id)},
    ])

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

    cycle = BillingCycle(
        society_id=society.id,
        name="May 2026 Maintenance",
        cycle_start="2026-05-01",
        cycle_end="2026-05-31",
        due_date="2026-06-10",
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
        bill_date="2026-05-01",
        due_date="2026-06-10",
        subtotal=1500,
        total_amount=1500,
        paid_amount=0,
        outstanding=1500,
    ))
    db.commit()

    _voucher(client, h, sid, [
        {"account_id": ledgers["members_dues"]["id"], "debit": "1500", "flat_id": str(flat.id)},
        {"account_id": ledgers["service_charges"]["id"], "credit": "1500"},
    ])

    r = client.get(f"{API}/members/{sid}/{flat.id}/ar-statement", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["member_account_number"].startswith("10")
    assert data["closing_ar"] == "1500.00"
    assert data["operational_outstanding"] == "1500.00"
    assert len(data["lines"]) == 1
    assert data["lines"][0]["debit"] == "1500.00"
    assert data["bills"][0]["invoice_number"] == "AR-TEST-0002"
