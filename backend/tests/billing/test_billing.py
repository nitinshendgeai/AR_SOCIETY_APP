"""Billing module tests — financial periods, charge configs, bill generation, payments."""
import pytest
from datetime import date, timedelta
from tests.conftest import make_user, make_society, make_wing, make_flat


def _make_flat_in_society(db, society):
    wing = make_wing(db, society.id, "Billing Wing")
    return make_flat(db, wing.id, "B101")


def test_create_financial_period(client, db):
    admin   = make_user(db, "adm@bil.com", role="Admin")
    society = make_society(db, "Billing Society 1")
    r = client.post("/api/v1/billing/periods",
                    json={
                        "society_id": str(society.id),
                        "name": "FY 2026",
                        "period_start": "2026-04-01",
                        "period_end": "2027-03-31",
                    },
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["name"] == "FY 2026"
    assert r.json()["is_closed"] is False


def test_resident_cannot_create_period(client, db):
    resident = make_user(db, "res@bil.com", role="Resident")
    society  = make_society(db, "Billing Society 2")
    r = client.post("/api/v1/billing/periods",
                    json={
                        "society_id": str(society.id),
                        "name": "FY 2026",
                        "period_start": "2026-04-01",
                        "period_end": "2027-03-31",
                    },
                    headers=resident["headers"])
    assert r.status_code == 403


def test_create_charge_config(client, db):
    admin   = make_user(db, "adm2@bil.com", role="Admin")
    society = make_society(db, "Billing Society 3")
    r = client.post("/api/v1/billing/charges",
                    json={
                        "society_id": str(society.id),
                        "charge_type": "maintenance",
                        "name": "Monthly Maintenance",
                        "default_amount": "2500.00",
                        "is_mandatory": True,
                        "tax_percent": "0",
                    },
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["name"] == "Monthly Maintenance"


def test_list_charge_configs(client, db):
    admin   = make_user(db, "adm3@bil.com", role="Admin")
    society = make_society(db, "Billing Society 4")

    for charge in [("maintenance", "Maint", "1500"), ("water", "Water", "200")]:
        client.post("/api/v1/billing/charges",
                    json={
                        "society_id": str(society.id),
                        "charge_type": charge[0],
                        "name": charge[1],
                        "default_amount": charge[2],
                        "tax_percent": "0",
                    },
                    headers=admin["headers"])

    r = client.get(f"/api/v1/billing/charges/{society.id}", headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_create_billing_cycle(client, db):
    admin   = make_user(db, "adm4@bil.com", role="Admin")
    society = make_society(db, "Billing Society 5")
    today   = date.today()

    r = client.post("/api/v1/billing/cycles",
                    json={
                        "society_id": str(society.id),
                        "name": "June 2026",
                        "cycle_start": str(today),
                        "cycle_end": str(today + timedelta(days=29)),
                        "due_date": str(today + timedelta(days=15)),
                    },
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["name"] == "June 2026"
    assert r.json()["is_finalized"] is False


def test_generate_bills_for_cycle(client, db):
    """Full bill generation: charge config + flat + cycle → bills created."""
    admin   = make_user(db, "adm5@bil.com", role="Admin")
    society = make_society(db, "Billing Society 6")
    today   = date.today()

    # Setup flat
    _make_flat_in_society(db, society)

    # Charge config
    client.post("/api/v1/billing/charges",
                json={
                    "society_id": str(society.id),
                    "charge_type": "maintenance",
                    "name": "Monthly",
                    "default_amount": "3000.00",
                    "tax_percent": "0",
                },
                headers=admin["headers"])

    # Billing cycle
    r_cycle = client.post("/api/v1/billing/cycles",
                          json={
                              "society_id": str(society.id),
                              "name": "June 2026",
                              "cycle_start": str(today),
                              "cycle_end": str(today + timedelta(days=29)),
                              "due_date": str(today + timedelta(days=15)),
                          },
                          headers=admin["headers"])
    cycle_id = r_cycle.json()["id"]

    # Generate bills
    r = client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills",
                    headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["bills_generated"] == 1


def test_duplicate_bill_generation_prevented(client, db):
    admin   = make_user(db, "adm6@bil.com", role="Admin")
    society = make_society(db, "Billing Society 7")
    today   = date.today()

    _make_flat_in_society(db, society)

    client.post("/api/v1/billing/charges",
                json={
                    "society_id": str(society.id),
                    "charge_type": "maintenance",
                    "name": "Monthly",
                    "default_amount": "2000.00",
                    "tax_percent": "0",
                },
                headers=admin["headers"])

    r_cycle = client.post("/api/v1/billing/cycles",
                          json={
                              "society_id": str(society.id),
                              "name": "July 2026",
                              "cycle_start": str(today),
                              "cycle_end": str(today + timedelta(days=29)),
                              "due_date": str(today + timedelta(days=15)),
                          },
                          headers=admin["headers"])
    cycle_id = r_cycle.json()["id"]

    client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills",
                headers=admin["headers"])

    # Second generate — must fail
    r2 = client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills",
                     headers=admin["headers"])
    assert r2.status_code == 409


def test_generate_bills_no_charge_config(client, db):
    """Generating bills without any charge config returns 422."""
    admin   = make_user(db, "adm7@bil.com", role="Admin")
    society = make_society(db, "Billing Society 8")
    today   = date.today()

    _make_flat_in_society(db, society)

    r_cycle = client.post("/api/v1/billing/cycles",
                          json={
                              "society_id": str(society.id),
                              "name": "August 2026",
                              "cycle_start": str(today),
                              "cycle_end": str(today + timedelta(days=29)),
                              "due_date": str(today + timedelta(days=15)),
                          },
                          headers=admin["headers"])
    cycle_id = r_cycle.json()["id"]

    r = client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills",
                    headers=admin["headers"])
    assert r.status_code == 422


def test_record_payment_and_update_outstanding(client, db):
    """Payment recording should reduce bill outstanding and update due tracker."""
    admin   = make_user(db, "adm8@bil.com", role="Admin")
    society = make_society(db, "Billing Society 9")
    today   = date.today()

    _make_flat_in_society(db, society)

    client.post("/api/v1/billing/charges",
                json={
                    "society_id": str(society.id),
                    "charge_type": "maintenance",
                    "name": "Monthly",
                    "default_amount": "2500.00",
                    "tax_percent": "0",
                },
                headers=admin["headers"])

    r_cycle = client.post("/api/v1/billing/cycles",
                          json={
                              "society_id": str(society.id),
                              "name": "Sep 2026",
                              "cycle_start": str(today),
                              "cycle_end": str(today + timedelta(days=29)),
                              "due_date": str(today + timedelta(days=15)),
                          },
                          headers=admin["headers"])
    cycle_id = r_cycle.json()["id"]

    client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills",
                headers=admin["headers"])

    # Get first bill
    from app.modules.billing.models.billing import MaintenanceBill
    bill = db.query(MaintenanceBill).first()
    assert bill is not None

    # Issue the bill
    client.post(f"/api/v1/billing/bills/{bill.id}/issue",
                headers=admin["headers"])

    # Record payment
    r_pay = client.post("/api/v1/billing/payments",
                        json={
                            "bill_id": str(bill.id),
                            "amount": "2500.00",
                            "payment_date": str(today),
                            "payment_mode": "upi",
                            "transaction_ref": "UPI12345",
                        },
                        headers=admin["headers"])
    assert r_pay.status_code == 201

    # Check bill is now PAID
    r_bill = client.get(f"/api/v1/billing/bills/{bill.id}",
                        headers=admin["headers"])
    assert r_bill.json()["bill_status"] == "paid"


def test_close_period(client, db):
    admin   = make_user(db, "adm9@bil.com", role="Admin")
    society = make_society(db, "Billing Society 10")

    r = client.post("/api/v1/billing/periods",
                    json={
                        "society_id": str(society.id),
                        "name": "FY 2025",
                        "period_start": "2025-04-01",
                        "period_end": "2026-03-31",
                    },
                    headers=admin["headers"])
    pid = r.json()["id"]

    r2 = client.post(f"/api/v1/billing/periods/{pid}/close",
                     headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["is_closed"] is True


def test_close_period_idempotent(client, db):
    """Closing an already-closed period returns 409."""
    admin   = make_user(db, "adm10@bil.com", role="Admin")
    society = make_society(db, "Billing Society 11")

    r = client.post("/api/v1/billing/periods",
                    json={
                        "society_id": str(society.id),
                        "name": "FY 2024",
                        "period_start": "2024-04-01",
                        "period_end": "2025-03-31",
                    },
                    headers=admin["headers"])
    pid = r.json()["id"]

    client.post(f"/api/v1/billing/periods/{pid}/close", headers=admin["headers"])
    r2 = client.post(f"/api/v1/billing/periods/{pid}/close", headers=admin["headers"])
    assert r2.status_code == 409
