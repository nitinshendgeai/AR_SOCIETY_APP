"""Maintenance element master — seeding, editing, custom elements, and
creating charge heads from elements (singly and in bulk)."""
from tests.conftest import make_user, make_society, make_wing, make_flat


def _rig(db, tag):
    society = make_society(db, f"Elem Society {tag}")
    wing = make_wing(db, society.id, "A")
    f = make_flat(db, wing.id, "101")
    f.area_sqft = 1000
    db.commit()
    admin = make_user(db, f"admin@el{tag}.com", role="Society Admin")
    manager = make_user(db, f"mgr@el{tag}.com", role="Manager")
    return society, admin["headers"], manager["headers"]


def _elements(client, h, society_id, **params):
    r = client.get(f"/api/v1/billing/elements/{society_id}", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _by_code(elements):
    return {e["code"]: e for e in elements}


def test_first_read_seeds_standard_bye_law_elements_once(client, db):
    society, admin, manager = _rig(db, "s1")
    first = _by_code(_elements(client, manager, society.id))
    assert {"service_charges", "sinking_fund", "repair_fund", "property_tax",
            "lift_maintenance", "parking", "water_charges"} <= set(first)
    assert first["sinking_fund"]["default_basis"] == "construction_cost_pct"
    assert first["sinking_fund"]["default_amount"] == "0.25"
    assert first["repair_fund"]["default_amount"] == "0.75"
    assert first["service_charges"]["is_service_charge"] is True
    assert all(e["is_system"] for e in first.values())
    assert len(_elements(client, manager, society.id)) == len(first)


def test_admin_can_edit_and_deactivate_a_standard_element(client, db):
    society, admin, manager = _rig(db, "s2")
    lift = _by_code(_elements(client, admin, society.id))["lift_maintenance"]
    r = client.patch(f"/api/v1/billing/elements/{lift['id']}",
                     json={"name": "Lift AMC", "default_basis": "fixed", "default_amount": "350"},
                     headers=admin)
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["default_basis"], r.json()["default_amount"]) == ("Lift AMC", "fixed", "350.00")
    client.patch(f"/api/v1/billing/elements/{lift['id']}", json={"is_active": False}, headers=admin)
    assert "lift_maintenance" not in _by_code(_elements(client, admin, society.id))
    assert "lift_maintenance" in _by_code(_elements(client, admin, society.id, include_inactive=True))


def test_admin_adds_custom_element_with_unique_code(client, db):
    society, admin, manager = _rig(db, "s3")
    body = {"society_id": str(society.id), "name": "Festival Fund", "category": "other",
            "default_basis": "fixed", "default_amount": "100"}
    a = client.post("/api/v1/billing/elements", json=body, headers=admin)
    b = client.post("/api/v1/billing/elements", json=body, headers=admin)
    assert a.status_code == b.status_code == 201
    assert (a.json()["code"], b.json()["code"]) == ("festival_fund", "festival_fund_2")
    assert a.json()["is_system"] is False


def test_manager_can_read_but_not_edit_the_master(client, db):
    society, admin, manager = _rig(db, "s4")
    el = _elements(client, manager, society.id)[0]
    r = client.patch(f"/api/v1/billing/elements/{el['id']}", json={"name": "X"}, headers=manager)
    assert r.status_code == 403
    r = client.post("/api/v1/billing/elements", json={"society_id": str(society.id), "name": "X"}, headers=manager)
    assert r.status_code == 403


def test_charge_head_from_element_inherits_defaults(client, db):
    society, admin, manager = _rig(db, "c1")
    sinking = _by_code(_elements(client, manager, society.id))["sinking_fund"]
    r = client.post("/api/v1/billing/charges", json={
        "society_id": str(society.id), "element_id": sinking["id"],
    }, headers=manager)
    assert r.status_code == 201, r.text
    c = r.json()
    assert (c["name"], c["charge_type"], c["basis"], c["default_amount"]) == \
        ("Sinking Fund", "sinking_fund", "construction_cost_pct", "0.25")
    assert c["element_id"] == sinking["id"] and c["element_name"] == "Sinking Fund"


def test_charge_head_from_element_can_override_defaults(client, db):
    society, admin, manager = _rig(db, "c2")
    svc = _by_code(_elements(client, manager, society.id))["service_charges"]
    r = client.post("/api/v1/billing/charges", json={
        "society_id": str(society.id), "element_id": svc["id"],
        "name": "Society Service Charges", "default_amount": "1800",
    }, headers=manager)
    c = r.json()
    assert (c["name"], c["default_amount"], c["is_service_charge"]) == ("Society Service Charges", "1800.00", True)


def test_charge_head_needs_element_or_type_and_name(client, db):
    society, admin, manager = _rig(db, "c3")
    r = client.post("/api/v1/billing/charges", json={
        "society_id": str(society.id), "default_amount": "100",
    }, headers=manager)
    assert r.status_code == 422


def test_bulk_load_creates_heads_and_skips_elements_in_use(client, db):
    society, admin, manager = _rig(db, "b1")
    els = _by_code(_elements(client, manager, society.id))
    items = [
        {"element_id": els["service_charges"]["id"], "amount": "1500"},
        {"element_id": els["sinking_fund"]["id"]},           # uses the 0.25% default
    ]
    r = client.post("/api/v1/billing/charges/from-elements",
                    json={"society_id": str(society.id), "items": items}, headers=manager)
    assert r.status_code == 201, r.text
    assert sorted(c["name"] for c in r.json()) == ["Service Charges", "Sinking Fund"]

    again = client.post("/api/v1/billing/charges/from-elements",
                        json={"society_id": str(society.id), "items": items}, headers=manager)
    assert again.status_code == 201 and again.json() == []
    assert len(client.get(f"/api/v1/billing/charges/{society.id}", headers=manager).json()) == 2


def test_bulk_load_requires_amount_when_element_has_no_default(client, db):
    society, admin, manager = _rig(db, "b2")
    els = _by_code(_elements(client, manager, society.id))
    r = client.post("/api/v1/billing/charges/from-elements", json={
        "society_id": str(society.id),
        "items": [{"element_id": els["property_tax"]["id"]}, {"element_id": els["sinking_fund"]["id"]}],
    }, headers=manager)
    assert r.status_code == 422
    assert "Property Tax" in r.json()["detail"]
    assert client.get(f"/api/v1/billing/charges/{society.id}", headers=manager).json() == []


def test_bulk_load_rejects_other_societys_element(client, db):
    society, admin, manager = _rig(db, "b3")
    other, _, other_mgr = _rig(db, "b3o")
    foreign = _elements(client, other_mgr, other.id)[0]
    r = client.post("/api/v1/billing/charges/from-elements", json={
        "society_id": str(society.id), "items": [{"element_id": foreign["id"], "amount": "10"}],
    }, headers=manager)
    assert r.status_code == 422
