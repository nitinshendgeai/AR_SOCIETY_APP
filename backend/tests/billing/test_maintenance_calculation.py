"""Maintenance calculation engine — every charge basis, non-occupancy, GST
threshold, interest on arrears, and the preview. Expected values are
worked out by hand in each test."""
from datetime import date, timedelta
from uuid import UUID
from app.models.flat import OccupancyStatus
from app.modules.billing.models.billing import MaintenanceBill
from app.modules.parking.models.parking import (
    ParkingZone, ParkingSlot, ParkingAllocation, SlotType, AllocationStatus,
)
from tests.conftest import make_user, make_society, make_wing, make_flat


def _rig(db, tag, areas=(600, 1200)):
    society = make_society(db, f"Calc Society {tag}")
    wing = make_wing(db, society.id, "A")
    flats = []
    for i, area in enumerate(areas):
        f = make_flat(db, wing.id, f"{i + 1}01")
        f.area_sqft = area
        f.occupancy_status = OccupancyStatus.OWNER_OCCUPIED
        flats.append(f)
    db.commit()
    manager = make_user(db, f"mgr@calc{tag}.com", role="Manager")
    return society, flats, manager["headers"]


def _charge(client, h, society_id, name, basis, amount, **extra):
    r = client.post("/api/v1/billing/charges", json={
        "society_id": str(society_id), "charge_type": extra.pop("charge_type", "maintenance"),
        "name": name, "basis": basis, "default_amount": str(amount), **extra,
    }, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _cycle(client, h, society_id, frequency="monthly", due_offset=10, name="Cycle"):
    today = date.today()
    r = client.post("/api/v1/billing/cycles", json={
        "society_id": str(society_id), "name": name, "frequency": frequency,
        "cycle_start": str(today), "cycle_end": str(today + timedelta(days=29)),
        "due_date": str(today + timedelta(days=due_offset)),
    }, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _settings(client, h, society_id, **changes):
    r = client.put(f"/api/v1/billing/maintenance-settings/{society_id}", json=changes, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _preview(client, h, cycle_id):
    r = client.get(f"/api/v1/billing/cycles/{cycle_id}/preview", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _totals(preview):
    return [f["total"] for f in preview["flats"]]


def test_fixed_charge_scales_with_cycle_months(client, db):
    society, flats, h = _rig(db, "fx")
    _charge(client, h, society.id, "Service Charges", "fixed", "1500")
    p = _preview(client, h, _cycle(client, h, society.id, frequency="quarterly"))
    assert p["months"] == 3
    assert _totals(p) == ["4500.00", "4500.00"]


def test_per_sqft_charge_uses_flat_area(client, db):
    society, flats, h = _rig(db, "sq")
    _charge(client, h, society.id, "Maintenance", "per_sqft", "3.50")
    p = _preview(client, h, _cycle(client, h, society.id))
    assert _totals(p) == ["2100.00", "4200.00"]   # 600 × 3.5, 1200 × 3.5


def test_construction_cost_pct_sinking_and_repair_fund(client, db):
    society, flats, h = _rig(db, "cc", areas=(1000,))
    _settings(client, h, society.id, construction_cost_per_sqft="2400")
    _charge(client, h, society.id, "Sinking Fund", "construction_cost_pct", "0.25", charge_type="sinking_fund")
    _charge(client, h, society.id, "Repair Fund", "construction_cost_pct", "0.75", charge_type="repair_fund")
    p = _preview(client, h, _cycle(client, h, society.id))
    lines = {l["description"]: l["amount"] for l in p["flats"][0]["lines"]}
    # 1000 sq ft × ₹2,400 = ₹24,00,000 construction cost
    assert lines["Sinking Fund"] == "500.00"    # × 0.25% ÷ 12
    assert lines["Repair Fund"] == "1500.00"    # × 0.75% ÷ 12


def test_construction_cost_pct_without_cost_warns_and_skips(client, db):
    society, flats, h = _rig(db, "cc2")
    _charge(client, h, society.id, "Service", "fixed", "1000")
    _charge(client, h, society.id, "Sinking Fund", "construction_cost_pct", "0.25")
    p = _preview(client, h, _cycle(client, h, society.id))
    assert _totals(p) == ["1000.00", "1000.00"]
    assert any("construction cost" in w for w in p["warnings"])


def test_annual_budget_split_equally_and_by_area(client, db):
    society, flats, h = _rig(db, "bud")
    _charge(client, h, society.id, "Security", "budget_equal", "120000")
    _charge(client, h, society.id, "Common Electricity", "budget_area", "180000")
    p = _preview(client, h, _cycle(client, h, society.id))
    small, large = p["flats"]
    s = {l["description"]: l["amount"] for l in small["lines"]}
    l = {l["description"]: l["amount"] for l in large["lines"]}
    assert s["Security"] == l["Security"] == "5000.00"       # 1,20,000 ÷ 2 ÷ 12
    assert s["Common Electricity"] == "5000.00"              # 1,80,000 × 600/1800 ÷ 12
    assert l["Common Electricity"] == "10000.00"             # 1,80,000 × 1200/1800 ÷ 12


def test_parking_charged_per_allotted_slot(client, db):
    society, flats, h = _rig(db, "pk")
    zone = ParkingZone(society_id=society.id, name="Basement")
    db.add(zone); db.flush()
    for i, charge in enumerate([None, 1200]):
        slot = ParkingSlot(society_id=society.id, zone_id=zone.id, slot_number=f"P{i}", slot_type=SlotType.RESIDENT)
        db.add(slot); db.flush()
        db.add(ParkingAllocation(society_id=society.id, slot_id=slot.id, flat_id=flats[0].id,
                                 allocation_type=SlotType.RESIDENT, status=AllocationStatus.ACTIVE,
                                 start_date=date.today(), monthly_charge=charge))
    db.commit()
    _charge(client, h, society.id, "Parking", "parking", "500", charge_type="parking")
    p = _preview(client, h, _cycle(client, h, society.id))
    # flat 1: one slot at the default ₹500 + one at its own ₹1,200; flat 2 has none
    assert [f["flat_label"] for f in p["flats"]] == ["A / 101"]
    assert p["flats"][0]["total"] == "1700.00"
    assert any("nothing to bill" in w for w in p["warnings"])


def test_non_occupancy_is_pct_of_service_charges_only(client, db):
    society, flats, h = _rig(db, "noc")
    flats[1].occupancy_status = OccupancyStatus.TENANT_OCCUPIED
    db.commit()
    _settings(client, h, society.id, non_occupancy_pct="10")
    _charge(client, h, society.id, "Service Charges", "fixed", "2000", is_service_charge=True)
    _charge(client, h, society.id, "Sinking Fund", "fixed", "800", charge_type="sinking_fund")
    p = _preview(client, h, _cycle(client, h, society.id))
    owner, tenant = p["flats"]
    assert owner["total"] == "2800.00"
    noc = [l for l in tenant["lines"] if l["description"].startswith("Non-occupancy")]
    assert noc[0]["amount"] == "200.00"          # 10% of 2000, not of 2800
    assert tenant["total"] == "3000.00"


def test_non_occupancy_above_ten_percent_rejected(client, db):
    society, flats, h = _rig(db, "noc2")
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}",
                   json={"non_occupancy_pct": "15"}, headers=h)
    assert r.status_code == 422


def test_interest_rate_above_legal_ceiling_rejected(client, db):
    society, flats, h = _rig(db, "int0")
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}",
                   json={"interest_rate_pct": "24"}, headers=h)
    assert r.status_code == 422


def test_gst_applies_to_whole_amount_only_above_threshold(client, db):
    society, flats, h = _rig(db, "gst")
    _settings(client, h, society.id, gst_enabled=True)
    # 600 sq ft × ₹12 = ₹7,200 (under ₹7,500); 1200 sq ft × ₹12 = ₹14,400 (over)
    _charge(client, h, society.id, "Maintenance", "per_sqft", "12")
    p = _preview(client, h, _cycle(client, h, society.id))
    small, large = p["flats"]
    assert small["tax"] == "0.00" and small["total"] == "7200.00"
    assert large["tax"] == "2592.00"             # 18% of the full 14,400
    assert large["total"] == "16992.00"


def test_gst_threshold_is_per_month_for_multi_month_cycles(client, db):
    society, flats, h = _rig(db, "gstq")
    _settings(client, h, society.id, gst_enabled=True)
    _charge(client, h, society.id, "Maintenance", "fixed", "5000")
    p = _preview(client, h, _cycle(client, h, society.id, frequency="quarterly"))
    # ₹15,000 for the quarter is still ₹5,000/month — no GST
    assert _totals(p) == ["15000.00", "15000.00"]


def test_interest_on_arrears_charged_once_per_period(client, db):
    society, flats, h = _rig(db, "arr", areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="12")
    _charge(client, h, society.id, "Maintenance", "fixed", "3650")

    # An earlier bill that fell due 30 days ago and is still unpaid
    first = _cycle(client, h, society.id, due_offset=-30, name="Earlier")
    client.post(f"/api/v1/billing/cycles/{first}/generate-bills", headers=h)
    client.post(f"/api/v1/billing/cycles/{first}/issue-all", headers=h)

    second = _cycle(client, h, society.id, name="Current")
    p = _preview(client, h, second)
    flat = p["flats"][0]
    interest = [l for l in flat["lines"] if l["description"].startswith("Interest on arrears")]
    assert interest[0]["amount"] == "36.00"       # 3,650 × 12% × 30/365
    assert flat["previous_dues"] == "3650.00"

    r = client.post(f"/api/v1/billing/cycles/{second}/generate-bills", headers=h)
    assert r.status_code == 200
    bills = client.get(f"/api/v1/billing/cycles/{second}/bills", headers=h).json()
    assert bills[0]["total_amount"] == "3686.00"
    assert bills[0]["previous_dues"] == "3650.00"

    # Same day, another cycle: those 30 days were already billed
    third = _cycle(client, h, society.id, name="Next")
    p3 = _preview(client, h, third)
    assert not any(l["description"].startswith("Interest") for l in p3["flats"][0]["lines"])


def test_no_interest_on_paid_or_unissued_bills(client, db):
    society, flats, h = _rig(db, "arr2", areas=(600,))
    _charge(client, h, society.id, "Maintenance", "fixed", "2000")
    first = _cycle(client, h, society.id, due_offset=-30, name="Unissued")
    client.post(f"/api/v1/billing/cycles/{first}/generate-bills", headers=h)
    p = _preview(client, h, _cycle(client, h, society.id, name="Current"))
    assert p["flats"][0]["total"] == "2000.00"


def test_preview_writes_nothing_and_matches_generation(client, db):
    society, flats, h = _rig(db, "pv")
    _charge(client, h, society.id, "Maintenance", "per_sqft", "4")
    cycle_id = _cycle(client, h, society.id)
    p = _preview(client, h, cycle_id)
    assert db.query(MaintenanceBill).filter(MaintenanceBill.cycle_id == UUID(cycle_id)).count() == 0
    client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h)
    bills = client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=h).json()
    assert sorted(b["total_amount"] for b in bills) == sorted(_totals(p))
    assert p["total"] == "7200.00"


def test_legacy_is_per_sqft_flag_maps_to_basis(client, db):
    society, flats, h = _rig(db, "leg")
    r = client.post("/api/v1/billing/charges", json={
        "society_id": str(society.id), "charge_type": "maintenance", "name": "Old style",
        "default_amount": "2", "is_per_sqft": True,
    }, headers=h)
    assert r.json()["basis"] == "per_sqft"
    r = client.patch(f"/api/v1/billing/charges/{r.json()['id']}", json={"basis": "fixed"}, headers=h)
    assert r.json()["is_per_sqft"] is False


def test_resident_cannot_change_maintenance_rules(client, db):
    society, flats, h = _rig(db, "rr")
    resident = make_user(db, "res@calcrr.com", role="Resident")
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}",
                   json={"interest_rate_pct": "5"}, headers=resident["headers"])
    assert r.status_code == 403
