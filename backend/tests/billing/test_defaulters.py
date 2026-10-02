"""Members' dues aged from the due date, the list of defaulters, and dues
reminders."""
from datetime import date, timedelta
from uuid import UUID

from app.models.notification import Notification
from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.defaulters import months_before
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig

API = "/api/v1/billing/defaulters"


def _two_cycles(client, db, tag):
    """Flat 101 (Asha Rao, has a login): ₹2,500 due 200 days ago and ₹2,500
    not yet due. Flat 102: ₹2,500 due 40 days ago and ₹2,500 not yet due."""
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    h = manager["headers"]
    assert client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={"interest_rate_pct": "0"},
                      headers=h).status_code == 200
    _charge(client, h, society.id, amount="2500.00")
    ids = []
    for name in ("Old cycle", "New cycle"):
        cycle_id = _cycle(client, h, society.id, name=name).json()["id"]
        assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
        assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
        ids.append(cycle_id)
    today = date.today()
    for flat, days in ((flat1, 200), (flat2, 40)):
        bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(ids[0]), flat_id=flat.id).one()
        bill.due_date = today - timedelta(days=days)
    db.commit()
    return society, flat1, flat2, manager, resident


def _row(data, flat):
    return next((r for r in data["flats"] if r["flat_id"] == str(flat.id)), None)


def test_dues_are_aged_and_defaulters_listed(client, db):
    society, flat1, flat2, manager, _res = _two_cycles(client, db, "df1")
    h, sid = manager["headers"], str(society.id)
    data = client.get(f"{API}/{sid}", headers=h).json()
    s = data["summary"]
    assert s["defaulters"] == 1 and s["flats_with_dues"] == 2
    assert s["total_outstanding"] == "10000.00" and s["in_default"] == "2500.00"
    assert [r["flat_id"] for r in data["flats"]] == [str(flat1.id)]
    r = _row(data, flat1)
    assert r["member_name"] == "Asha Rao" and r["is_defaulter"]
    assert r["buckets"]["m6_12"] == "2500.00" and r["buckets"]["not_due"] == "2500.00"
    assert r["total"] == "5000.00" and r["unpaid_bills"] == 2 and r["days_overdue"] == 200
    assert r["bills"][0]["bucket"] == "m6_12"
    buckets = {b["key"]: b["amount"] for b in s["buckets"]}
    assert buckets == {"not_due": "5000.00", "upto_3": "2500.00", "m3_6": "0.00", "m6_12": "2500.00",
                       "over_12": "0.00"}

    # Every flat with dues, or a shorter limit
    everyone = client.get(f"{API}/{sid}", params={"include_all": True}, headers=h).json()
    assert {r["flat_id"] for r in everyone["flats"]} == {str(flat1.id), str(flat2.id)}
    assert not _row(everyone, flat2)["is_defaulter"]
    one_month = client.get(f"{API}/{sid}", params={"min_months": 1}, headers=h).json()
    assert one_month["summary"]["defaulters"] == 2


def test_on_account_payment_set_off_against_oldest_dues(client, db):
    society, flat1, _flat2, manager, _res = _two_cycles(client, db, "df2")
    h, sid = manager["headers"], str(society.id)
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": str(flat1.id), "amount": "1000.00", "payment_date": str(date.today()), "payment_mode": "cash",
    }, headers=h)
    assert r.status_code == 201, r.text
    row = _row(client.get(f"{API}/{sid}", headers=h).json(), flat1)
    assert row["buckets"]["m6_12"] == "1500.00" and row["total"] == "4000.00"
    assert row["on_account"] == "1000.00"
    assert row["last_payment_date"] == str(date.today()) and row["last_payment_amount"] == "1000.00"

    # Paying the old bill in full takes the flat off the list
    old = db.query(MaintenanceBill).filter(MaintenanceBill.flat_id == flat1.id,
                                           MaintenanceBill.due_date < date.today()).one()
    r = client.post("/api/v1/billing/payments", json={
        "bill_id": str(old.id), "amount": "2500.00", "payment_date": str(date.today()), "payment_mode": "cash",
    }, headers=h)
    assert r.status_code == 201, r.text
    assert client.get(f"{API}/{sid}", headers=h).json()["summary"]["defaulters"] == 0


def test_reminders_go_to_defaulters_with_a_login(client, db):
    society, flat1, flat2, manager, resident = _two_cycles(client, db, "df3")
    h, sid = manager["headers"], str(society.id)
    r = client.post(f"{API}/{sid}/remind", json={}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"flats_reminded": 1, "notifications": 1, "flats_without_app_login": []}
    n = db.query(Notification).filter_by(user_id=resident["user"].id, module="billing_dues").one()
    assert n.title == "Maintenance dues reminder" and "₹5,000.00" in n.body
    assert _row(client.get(f"{API}/{sid}", headers=h).json(), flat1)["last_reminded_at"]

    # Chosen flats, even if not yet defaulters
    r = client.post(f"{API}/{sid}/remind", json={"flat_ids": [str(flat2.id)]}, headers=h)
    assert r.json()["flats_reminded"] == 1


def test_defaulters_pdf_and_permissions(client, db):
    society, _f1, _f2, manager, resident = _two_cycles(client, db, "df4")
    sid = str(society.id)
    r = client.get(f"{API}/{sid}", params={"format": "pdf"}, headers=manager["headers"])
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert client.get(f"{API}/{sid}", headers=resident["headers"]).status_code == 403
    assert client.post(f"{API}/{sid}/remind", json={}, headers=resident["headers"]).status_code == 403


def test_months_before_clamps_to_month_end():
    assert months_before(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert months_before(date(2026, 1, 15), 3) == date(2025, 10, 15)
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
