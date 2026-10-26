"""A charge head that is a % of the flat's own service-charge lines (repair fund 0.75%, sinking fund 0.25% of the
monthly maintenance). Expected values are worked out by hand."""
from app.models.flat import OccupancyStatus
from tests.billing.test_maintenance_calculation import (
    _charge, _cycle, _preview, _rig, _settings, _totals,
)


def _lines(flat, description):
    return [l["amount"] for l in flat["lines"] if l["description"] == description]


def _heads(client, h, society):
    _charge(client, h, society.id, "Service Charges", "fixed", "2000", is_service_charge=True)
    _charge(client, h, society.id, "Security", "fixed", "2000", is_service_charge=True)
    _charge(client, h, society.id, "Water", "fixed", "1000")                          # not a service charge
    _charge(client, h, society.id, "Repair Fund", "service_charge_pct", "0.75", charge_type="repair_fund")
    _charge(client, h, society.id, "Sinking Fund", "service_charge_pct", "0.25", charge_type="sinking_fund")


def test_the_funds_are_a_percentage_of_the_service_charge_lines_only(client, db):
    society, flats, h = _rig(db, "sp1")
    _heads(client, h, society)
    p = _preview(client, h, _cycle(client, h, society.id))
    for flat in p["flats"]:
        assert _lines(flat, "Repair Fund") == ["30.00"]          # 0.75% of 4000 (water is not a service charge)
        assert _lines(flat, "Sinking Fund") == ["10.00"]         # 0.25% of 4000
    assert _totals(p) == ["5040.00", "5040.00"]


def test_the_percentage_follows_the_months_billed(client, db):
    society, flats, h = _rig(db, "sp2")
    _heads(client, h, society)
    p = _preview(client, h, _cycle(client, h, society.id, frequency="quarterly"))
    assert p["months"] == 3
    assert _lines(p["flats"][0], "Repair Fund") == ["90.00"]     # 0.75% of 12000
    assert _lines(p["flats"][0], "Sinking Fund") == ["30.00"]


def test_the_funds_are_not_part_of_the_non_occupancy_base(client, db):
    society, flats, h = _rig(db, "sp3")
    flats[1].occupancy_status = OccupancyStatus.TENANT_OCCUPIED
    db.commit()
    _settings(client, h, society.id, non_occupancy_pct="10")
    _heads(client, h, society)
    owner, tenant = _preview(client, h, _cycle(client, h, society.id))["flats"]
    noc = [l["amount"] for l in tenant["lines"] if l["description"].startswith("Non-occupancy")]
    assert noc == ["400.00"]                                      # 10% of 4000, not of the funds
    assert tenant["total"] == "5440.00"


def test_with_no_service_charge_lines_the_funds_bill_nothing(client, db):
    society, flats, h = _rig(db, "sp4")
    _charge(client, h, society.id, "Water", "fixed", "1000")
    _charge(client, h, society.id, "Repair Fund", "service_charge_pct", "0.75", charge_type="repair_fund")
    p = _preview(client, h, _cycle(client, h, society.id))
    assert _lines(p["flats"][0], "Repair Fund") == [] and _totals(p) == ["1000.00", "1000.00"]


def test_it_cannot_bill_actual_expenses_and_survives_a_round_trip(client, db):
    society, flats, h = _rig(db, "sp5")
    head = _charge(client, h, society.id, "Repair Fund", "service_charge_pct", "0.75", charge_type="repair_fund")
    assert head["basis"] == "service_charge_pct" and head["default_amount"] == "0.75"
    r = client.patch(f"/api/v1/billing/charges/{head['id']}", json={"auto_from_expenses": True}, headers=h)
    assert r.status_code == 422
