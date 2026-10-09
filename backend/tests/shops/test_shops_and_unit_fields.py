"""Shops (a master of their own: owner, possession date, electricity meter, bulk import) and the possession date and
meter numbers a flat now carries."""
from datetime import date, timedelta

from tests.conftest import make_flat, make_society, make_user, make_wing

S = "/api/v1/shops"
F = "/api/v1/flats"


def _member(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who["headers"]


def _rig(db, tag):
    society = make_society(db, f"Shops Society {tag}")
    wing = make_wing(db, society.id, f"Wing {tag}")
    admin = _member(db, f"adm@shops{tag}.test", "Society Admin", society)
    return society, wing, admin


def _shop(client, h, number="S-1", **over):
    body = {"shop_number": number, "owner_name": "Mehta Traders", **over}
    return client.post(f"{S}/", headers=h, json=body)


# ── Shops: the master ────────────────────────────────────────────────────────

def test_a_shop_is_added_with_its_owner_possession_date_and_meter(client, db):
    society, _, h = _rig(db, "s1")
    r = _shop(client, h, "S-1", owner_phone="98765 43210", owner_email="m@x.in", floor=0, area_sqft=250,
              business_name="Mehta Stationers", occupancy="rented", tenant_name="Ravi", possession_date="2019-04-01",
              electric_meter_no="  MTR  001 ", electric_consumer_no="170012345678", location="Ground floor, Block C")
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["shop_number"] == "S-1" and s["owner_phone"] == "9876543210" and s["occupancy"] == "rented"
    assert s["possession_date"] == "2019-04-01" and s["electric_meter_no"] == "MTR 001"
    assert s["society_id"] == str(society.id)
    assert client.get(f"{S}/{s['id']}", headers=h).json()["business_name"] == "Mehta Stationers"
    assert _shop(client, h, "S-2").json()["occupancy"] == "vacant"          # unspecified: vacant


def test_the_list_is_in_shop_order_and_can_be_searched_and_filtered(client, db):
    society, _, h = _rig(db, "s2")
    for n, owner, occ, meter in (("S-10", "Gupta", "vacant", "M10"), ("S-2", "Shah", "rented", "M2"),
                                 ("S-1", "Iyer", "owner_run", None)):
        assert _shop(client, h, n, owner_name=owner, occupancy=occ, electric_meter_no=meter).status_code == 201
    rows = client.get(f"{S}/society/{society.id}", headers=h).json()
    assert [r["shop_number"] for r in rows] == ["S-1", "S-2", "S-10"]
    q = lambda **p: [r["shop_number"] for r in client.get(f"{S}/society/{society.id}", headers=h, params=p).json()]
    assert q(q="shah") == ["S-2"] and q(q="m10") == ["S-10"] and q(occupancy="vacant") == ["S-10"]


def test_a_shop_number_is_unique_in_a_society_until_the_shop_is_deleted(client, db):
    society, _, h = _rig(db, "s3")
    first = _shop(client, h, "S-1").json()
    assert _shop(client, h, "s-1").status_code == 409
    assert client.delete(f"{S}/{first['id']}", headers=h).status_code == 204
    assert _shop(client, h, "S-1").status_code == 201                       # the number is free again
    assert [r["shop_number"] for r in client.get(f"{S}/society/{society.id}", headers=h).json()] == ["S-1"]


def test_bad_values_are_refused(client, db):
    _, _, h = _rig(db, "s4")
    assert _shop(client, h, "S-1", owner_phone="12").status_code == 422
    assert _shop(client, h, "S-1", occupancy="closed down").status_code == 422
    assert _shop(client, h, "S-1", possession_date="1901-01-01").status_code == 422
    assert _shop(client, h, "S-1", possession_date=str(date.today() + timedelta(days=900))).status_code == 422
    assert _shop(client, h, "S-1", owner_name="   ").status_code == 422
    assert _shop(client, h, "S-1", area_sqft=0).status_code == 422


def test_editing_a_shop_changes_only_what_is_sent_and_can_clear_optional_fields(client, db):
    _, _, h = _rig(db, "s5")
    s = _shop(client, h, "S-1", business_name="Old Name", electric_meter_no="M1", possession_date="2020-01-01").json()
    r = client.patch(f"{S}/{s['id']}", headers=h, json={"business_name": "New Name"})
    assert r.json()["business_name"] == "New Name" and r.json()["electric_meter_no"] == "M1"
    r = client.patch(f"{S}/{s['id']}", headers=h, json={"electric_meter_no": None, "possession_date": None})
    assert r.json()["electric_meter_no"] is None and r.json()["possession_date"] is None
    assert r.json()["owner_name"] == "Mehta Traders"
    assert client.patch(f"{S}/{s['id']}", headers=h, json={"owner_name": None}).json()["owner_name"] == "Mehta Traders"
    _shop(client, h, "S-2")
    assert client.patch(f"{S}/{s['id']}", headers=h, json={"shop_number": "s-2"}).status_code == 409


def test_each_society_sees_only_its_own_shops_and_only_the_committee_manages_them(client, db):
    society, _, h = _rig(db, "s6")
    other = make_society(db, "Other Shops Society")
    theirs = _member(db, "adm@shops-other.test", "Society Admin", other)
    resident = _member(db, "res@shops-s6.test", "Resident", society)
    mine = _shop(client, h, "S-1").json()
    assert client.get(f"{S}/{mine['id']}", headers=theirs).status_code == 404
    assert client.patch(f"{S}/{mine['id']}", headers=theirs, json={"remarks": "x"}).status_code == 404
    assert client.delete(f"{S}/{mine['id']}", headers=theirs).status_code == 404
    assert client.get(f"{S}/society/{society.id}", headers=theirs).status_code == 403
    assert client.post(f"{S}/", headers=theirs, json={"society_id": str(society.id), "shop_number": "X",
                                                     "owner_name": "Y"}).status_code == 403
    assert client.get(f"{S}/society/{society.id}", headers=resident).status_code == 403
    assert _shop(client, resident, "S-9").status_code == 403


# ── Meters: one meter, one unit ──────────────────────────────────────────────

def test_a_meter_number_can_be_on_only_one_flat_or_shop_of_a_society(client, db):
    society, wing, h = _rig(db, "m1")
    flat = make_flat(db, wing.id, "101")
    other_flat = make_flat(db, wing.id, "102")
    r = client.patch(f"{F}/{flat.id}", headers=h, json={"electric_meter_no": "MTR-9", "electric_consumer_no": "C-1"})
    assert r.status_code == 200, r.text
    assert r.json()["electric_meter_no"] == "MTR-9" and r.json()["electric_consumer_no"] == "C-1"

    assert client.patch(f"{F}/{other_flat.id}", headers=h, json={"electric_meter_no": "mtr-9"}).status_code == 409
    assert _shop(client, h, "S-1", electric_meter_no="MTR-9").status_code == 409          # not on a shop either
    shop = _shop(client, h, "S-1", electric_meter_no="MTR-10").json()
    assert client.patch(f"{F}/{other_flat.id}", headers=h, json={"electric_meter_no": "MTR-10"}).status_code == 409
    assert client.patch(f"{S}/{shop['id']}", headers=h, json={"electric_meter_no": "MTR-9"}).status_code == 409
    # a consumer number can be shared (one account, several meters); a unit keeps its own meter on re-save
    assert client.patch(f"{F}/{other_flat.id}", headers=h, json={"electric_consumer_no": "C-1"}).status_code == 200
    assert client.patch(f"{F}/{flat.id}", headers=h, json={"electric_meter_no": "MTR-9"}).status_code == 200


def test_a_flat_carries_a_possession_date_that_can_be_changed_and_cleared(client, db):
    _, wing, h = _rig(db, "f1")
    made = client.post(f"{F}/", headers=h, json={"flat_number": "201", "wing_id": str(wing.id),
                                                 "possession_date": "2018-06-15"})
    assert made.status_code == 201, made.text
    assert made.json()["possession_date"] == "2018-06-15"
    fid = made.json()["id"]
    assert client.patch(f"{F}/{fid}", headers=h, json={"possession_date": "2018-07-01"}).json()["possession_date"] == "2018-07-01"
    assert client.patch(f"{F}/{fid}", headers=h, json={"floor": 2}).json()["possession_date"] == "2018-07-01"   # untouched
    assert client.patch(f"{F}/{fid}", headers=h, json={"possession_date": None}).json()["possession_date"] is None
    assert client.patch(f"{F}/{fid}", headers=h, json={"possession_date": "1899-01-01"}).status_code == 422


# ── Import ───────────────────────────────────────────────────────────────────

def _import(client, h, rows, dry_run=False, society=None):
    body = {"rows": [{"line": i + 2, **r} for i, r in enumerate(rows)], "dry_run": dry_run}
    if society:
        body["society_id"] = str(society.id)
    return client.post(f"{S}/import", headers=h, json=body)


def test_an_import_adds_new_shops_and_fills_in_existing_ones_and_reports_each_row(client, db):
    society, _, h = _rig(db, "i1")
    _shop(client, h, "S-1", owner_name="Old Owner", business_name="Keep Me", electric_meter_no="M-1")
    r = _import(client, h, [
        {"shop_number": "S-1", "possession_date": "2019-04-01", "owner_phone": "9876543210"},   # exists: fill in
        {"shop_number": "S-2", "owner_name": "Shah", "floor": "Ground", "area_sqft": "1,250.5", "occupancy": "Rented",
         "possession_date": "2020-02-29", "electric_meter_no": "M-2"},
        {"shop_number": "S-3", "owner_name": "", },                                              # new, no owner
        {"shop_number": "S-4", "owner_name": "Iyer", "possession_date": "31-01-2020"},           # not ISO
        {"shop_number": "S-2", "owner_name": "Dup"},                                             # twice in the file
        {"shop_number": "S-5", "owner_name": "Rao", "electric_meter_no": "M-1"},                 # meter taken by S-1
        {"owner_name": "No Number"},
    ])
    assert r.status_code == 200, r.text
    got = [(x["shop_number"], x["status"]) for x in r.json()]
    assert got == [("S-1", "updated"), ("S-2", "created"), ("S-3", "error"), ("S-4", "error"), ("S-2", "error"),
                   ("S-5", "error"), (None, "error")]
    msgs = {x["shop_number"]: x["message"] for x in r.json() if x["message"]}
    assert "Owner name" in msgs["S-3"] and "date" in msgs["S-4"].lower() and "Meter M-1" in msgs["S-5"]

    shops = {s["shop_number"]: s for s in client.get(f"{S}/society/{society.id}", headers=h).json()}
    assert set(shops) == {"S-1", "S-2"}
    s1, s2 = shops["S-1"], shops["S-2"]
    assert s1["owner_name"] == "Old Owner" and s1["business_name"] == "Keep Me"        # not wiped
    assert s1["possession_date"] == "2019-04-01" and s1["owner_phone"] == "9876543210"  # filled in
    assert s2["floor"] == 0 and s2["area_sqft"] == 1250.5 and s2["occupancy"] == "rented"
    assert s2["possession_date"] == "2020-02-29" and s2["electric_meter_no"] == "M-2"


def test_a_dry_run_checks_every_row_and_writes_nothing(client, db):
    society, _, h = _rig(db, "i2")
    r = _import(client, h, [{"shop_number": "S-1", "owner_name": "A"}, {"shop_number": "S-2"}], dry_run=True)
    assert [x["status"] for x in r.json()] == ["created", "error"]
    assert client.get(f"{S}/society/{society.id}", headers=h).json() == []


def test_importing_into_another_society_is_refused(client, db):
    society, _, h = _rig(db, "i3")
    other = make_society(db, "Elsewhere")
    assert _import(client, h, [{"shop_number": "S-1", "owner_name": "A"}], society=other).status_code == 403
    resident = _member(db, "res@shops-i3.test", "Resident", society)
    assert _import(client, resident, [{"shop_number": "S-1", "owner_name": "A"}]).status_code == 403
