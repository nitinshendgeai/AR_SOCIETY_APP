"""The Manager runs the whole maintenance module: periods, the element
master, charge heads, rules, cycles, generating and issuing bills,
recording payments, dues and interest rules. Residents still can't."""
from datetime import date, timedelta
from uuid import UUID

from app.modules.billing.models.billing import MaintenanceBill
from tests.billing.test_maintenance_billing import _rig


def test_manager_runs_maintenance_billing_end_to_end(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "mgr1")
    h, sid, today = manager["headers"], str(society.id), date.today()

    r = client.post("/api/v1/billing/periods", json={
        "society_id": sid, "name": "FY 2026-27", "period_start": "2026-04-01", "period_end": "2027-03-31",
    }, headers=h)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/v1/billing/periods/{sid}", headers=h).status_code == 200

    # The element master: add one, edit it, then bill from it
    r = client.post("/api/v1/billing/elements", json={
        "society_id": sid, "name": "Service Charges", "category": "maintenance",
        "default_basis": "fixed", "default_amount": "2000",
    }, headers=h)
    assert r.status_code == 201, r.text
    element = r.json()
    r = client.patch(f"/api/v1/billing/elements/{element['id']}", json={"default_amount": "2200"}, headers=h)
    assert r.status_code == 200 and r.json()["default_amount"] == "2200.00", r.text
    r = client.post("/api/v1/billing/charges", json={"society_id": sid, "element_id": element["id"]}, headers=h)
    assert r.status_code == 201, r.text

    r = client.put(f"/api/v1/billing/maintenance-settings/{sid}", json={"interest_rate_pct": "18"}, headers=h)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/billing/penalty-rules", json={"society_id": sid, "name": "Late fee", "rate": "2"},
                    headers=h)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/v1/billing/penalty-rules/{sid}", headers=h).status_code == 200

    r = client.post("/api/v1/billing/cycles", json={
        "society_id": sid, "name": "Oct 2026", "cycle_start": str(today),
        "cycle_end": str(today + timedelta(days=30)), "due_date": str(today + timedelta(days=10)),
    }, headers=h)
    assert r.status_code == 201, r.text
    cycle_id = r.json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200

    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    assert bill.total_amount == 2200
    r = client.post("/api/v1/billing/payments", json={
        "bill_id": str(bill.id), "amount": "2200.00", "payment_date": str(today),
        "payment_mode": "cheque", "cheque_number": "004512", "bank_name": "UBI",
    }, headers=h)
    assert r.status_code == 201, r.text
    receipt_no = r.json()["receipt_number"]

    assert client.get(f"/api/v1/billing/dues/outstanding/{sid}", headers=h).status_code == 200
    assert client.get(f"/api/v1/billing/bills/{bill.id}/pdf", headers=h).status_code == 200
    assert client.get(f"/api/v1/billing/receipts/{receipt_no}/pdf", headers=h).status_code == 200


def test_resident_cannot_run_billing(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "mgr2")
    h, sid = resident["headers"], str(society.id)
    assert client.post("/api/v1/billing/elements", json={"society_id": sid, "name": "X"}, headers=h).status_code == 403
    assert client.get(f"/api/v1/billing/dues/outstanding/{sid}", headers=h).status_code == 403
    assert client.get(f"/api/v1/billing/penalty-rules/{sid}", headers=h).status_code == 403
    assert client.post("/api/v1/billing/cycles", json={
        "society_id": sid, "name": "X", "cycle_start": "2026-10-01", "cycle_end": "2026-10-31",
        "due_date": "2026-10-10",
    }, headers=h).status_code == 403
