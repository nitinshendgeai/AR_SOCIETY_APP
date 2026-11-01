"""Tower parking billing: a charge head tied to a parking zone (Tower Parking AMC, parking-meter electricity, wallet,
fire AMC...) is billed only to the flats holding a slot in that zone, per slot held. Everyone else is untouched."""
from datetime import date, timedelta
from decimal import Decimal

from app.modules.parking.models.parking import ParkingZone
from tests.billing.test_budget_suggestions import _bill, _charge_from_element, _rig as _expense_rig
from tests.billing.test_maintenance_calculation import _charge, _cycle, _preview, _rig
from tests.billing.test_period_expense_billing import _cycle_dates
from tests.billing.test_two_wheeler_parking import _slot

B = "/api/v1/billing"
D = Decimal


def _zone(db, society, name="Tower"):
    z = ParkingZone(society_id=society.id, name=name)
    db.add(z)
    db.flush()
    return z


def _amounts(preview):
    """flat label -> {line description: amount}"""
    return {f["flat_label"]: {l["description"]: l["amount"] for l in f["lines"]} for f in preview["flats"]}


def test_a_zone_head_bills_only_tower_holders_per_slot_held(client, db):
    society, flats, h = _rig(db, "z1", areas=(600, 1200, 900))
    tower, basement = _zone(db, society), _zone(db, society, "Basement")
    _slot(db, society, tower, flats[0], "T1")
    _slot(db, society, tower, flats[0], "T2")          # flat 0 holds two tower slots
    _slot(db, society, tower, flats[1], "T3")
    _slot(db, society, basement, flats[2], "B1")       # flat 2 is not a tower holder
    db.commit()
    head = _charge(client, h, society.id, "Tower Parking AMC", "fixed", "250", charge_type="parking",
                   parking_zone_id=str(tower.id))
    assert head["parking_zone_id"] == str(tower.id) and head["parking_zone_name"] == "Tower"
    p = _amounts(_preview(client, h, _cycle(client, h, society.id)))
    got = {label: lines["Tower Parking AMC"] for label, lines in p.items()}
    assert sorted(got.values()) == ["250.00", "500.00"]                        # 1 slot -> 250, 2 slots -> 500
    assert len(got) == 2                                                       # the basement holder has no bill line


def test_an_equal_budget_zone_head_shares_the_year_over_the_slots(client, db):
    society, flats, h = _rig(db, "z2")
    tower = _zone(db, society)
    _slot(db, society, tower, flats[0], "T1")
    _slot(db, society, tower, flats[0], "T2")
    _slot(db, society, tower, flats[1], "T3")
    db.commit()
    _charge(client, h, society.id, "Tower Fire AMC", "budget_equal", "3600", charge_type="parking",
            parking_zone_id=str(tower.id))
    p = _amounts(_preview(client, h, _cycle(client, h, society.id)))
    # 3600 a year over 3 slots = 100 a slot a month
    assert sorted(l["Tower Fire AMC"] for l in p.values()) == ["100.00", "200.00"]


def test_zone_head_rules(client, db):
    society, flats, h = _rig(db, "z3")
    other_society, _, _ = _rig(db, "z3b")
    tower, foreign = _zone(db, society), _zone(db, other_society)
    db.commit()
    body = {"society_id": str(society.id), "charge_type": "parking", "name": "X", "default_amount": "10"}
    r = client.post(f"{B}/charges", json={**body, "basis": "fixed", "parking_zone_id": str(foreign.id)}, headers=h)
    assert r.status_code == 422                                                # another society's zone
    r = client.post(f"{B}/charges", json={**body, "basis": "per_sqft", "parking_zone_id": str(tower.id)}, headers=h)
    assert r.status_code == 422                                                # per-slot needs fixed / equal budget
    r = client.post(f"{B}/charges", json={**body, "basis": "fixed", "parking_zone_id": str(tower.id)}, headers=h)
    assert r.status_code == 201
    r = client.patch(f"{B}/charges/{r.json()['id']}", json={"parking_zone_id": None}, headers=h)
    assert r.status_code == 200 and r.json()["parking_zone_id"] is None        # clearing it makes it a normal head


def test_the_tower_parking_elements_are_in_the_master(client, db):
    society, admin, manager, _ = _expense_rig(db, "z4")
    codes = {e["code"] for e in client.get(f"{B}/elements/{society.id}", headers=manager).json()}
    assert {"tower_parking_amc", "tower_parking_electricity", "tower_parking_wallet",
            "tower_parking_fire_amc"} <= codes


def test_a_period_zone_head_shares_the_actual_spend_over_tower_slots_only(client, db):
    society, admin, manager, _ = _expense_rig(db, "z5")                       # three flats: 101, 102, 201
    from app.models.flat import Flat
    flats = sorted(db.query(Flat).filter(Flat.wing.has(society_id=society.id)).all(), key=lambda f: f.flat_number)
    tower = _zone(db, society)
    _slot(db, society, tower, flats[0], "T1")
    _slot(db, society, tower, flats[0], "T2")
    _slot(db, society, tower, flats[1], "T3")
    db.commit()
    head = _charge_from_element(client, manager, society.id, "housekeeping", basis="fixed", default_amount="1",
                                auto_from_expenses=True, expense_mode="period", parking_zone_id=str(tower.id))
    today = date.today()
    cycle_id = _cycle_dates(client, manager, society.id, today - timedelta(days=10), today + timedelta(days=20), "Z5")
    _bill(client, admin, society.id, "housekeeping", "9000.00", today)
    pv = client.get(f"{B}/cycles/{cycle_id}/preview", headers=manager).json()
    lines = {f["flat_label"]: l["amount"] for f in pv["flats"] for l in f["lines"] if l["description"] == head["name"]}
    assert sorted(D(v) for v in lines.values()) == [D("3000"), D("6000")]      # 9000 over 3 slots; flat 201 pays none
    assert len(lines) == 2


def test_tower_parking_preview_lists_only_tower_holders_with_their_parking_lines(client, db):
    society, flats, h = _rig(db, "z6", areas=(600, 1200, 900))
    tower, basement = _zone(db, society), _zone(db, society, "Basement")
    _slot(db, society, tower, flats[0], "T1")
    _slot(db, society, tower, flats[0], "T2")
    _slot(db, society, tower, flats[1], "T3")
    _slot(db, society, basement, flats[2], "B1")
    db.commit()
    _charge(client, h, society.id, "Maintenance", "fixed", "2000")
    _charge(client, h, society.id, "Tower Parking AMC", "fixed", "400", charge_type="parking",
            parking_zone_id=str(tower.id))
    _charge(client, h, society.id, "Tower Parking Fire AMC", "fixed", "150", charge_type="parking",
            parking_zone_id=str(tower.id))
    cycle_id = _cycle(client, h, society.id)
    r = client.get(f"{B}/cycles/{cycle_id}/tower-parking-preview", headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    assert [z["zone_name"] for z in p["zones"]] == ["Tower"]
    assert p["zones"][0]["holders"] == 2 and p["zones"][0]["slots"] == 3
    assert sorted(D(f["total"]) for f in p["flats"]) == [D("550"), D("1100")]
    two = next(f for f in p["flats"] if f["slots"] == 2)
    assert {l["description"]: l["amount"] for l in two["lines"]} == {
        "Tower Parking AMC": "800.00", "Tower Parking Fire AMC": "300.00"}
    assert all(l["is_zone_head"] for l in two["lines"])                       # maintenance is not a parking line
    assert p["total"] == "1650.00"
    assert client.get(f"{B}/cycles/{cycle_id}/tower-parking-preview").status_code in (401, 403)


def test_tower_parking_preview_without_zone_heads_is_empty(client, db):
    society, flats, h = _rig(db, "z7")
    _charge(client, h, society.id, "Maintenance", "fixed", "2000")
    p = client.get(f"{B}/cycles/{_cycle(client, h, society.id)}/tower-parking-preview", headers=h).json()
    assert p["zones"] == [] and p["flats"] == [] and p["total"] == "0.00"
