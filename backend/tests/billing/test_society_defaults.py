"""A new society, and one whose data was cleaned, starts with the standard maintenance elements and every standard
expense ledger linked to the element it pays for - without anyone opening the billing screens first."""
from app.modules.accounts.models.accounts import Account
from app.modules.billing.models.billing import MaintenanceElement
from app.modules.accounts.services.chart_of_accounts import seed_society_defaults
from tests.conftest import make_user, place_in
from tests.platform_admin.test_society_purge import P, _seed, make_superadmin

LINKS = {
    "security_charges": "security", "cctv_maintenance": "cctv", "housekeeping": "housekeeping",
    "garden": "housekeeping", "pest_control": "pest_control", "fire_safety": "fire_safety", "lift_maintenance": "lift_maintenance",
    "electricity": "common_electricity", "generator_maintenance": "common_electricity",
    "water_charges": "water_charges", "property_tax": "property_tax", "insurance": "insurance",
    "lease_rent": "lease_rent_na_tax",
    "salaries": "service_charges", "audit_fees": "service_charges", "legal_fees": "service_charges",
    "printing_stationery": "service_charges", "postage_telephone": "service_charges",
    "office_expenses": "service_charges", "meeting_expenses": "service_charges",
    "computer_expenses": "service_charges", "misc_expenses": "service_charges",
}
UNLINKED = ("repairs_building", "repairs_electrical", "repairs_plumbing", "repairs_general", "bank_charges",
            "interest_on_loans", "depreciation")


def _assert_defaults(db, society_id):
    elements = {e.id: e for e in db.query(MaintenanceElement).filter_by(society_id=society_id)}
    assert len(elements) == 17
    by_code = {e.code: e for e in elements.values()}
    assert (by_code["repair_fund"].default_basis.value, str(by_code["repair_fund"].default_amount)) == \
        ("service_charge_pct", "0.75")
    assert (by_code["sinking_fund"].default_basis.value, str(by_code["sinking_fund"].default_amount)) == \
        ("service_charge_pct", "0.25")
    assert {c for c, e in by_code.items() if e.is_service_charge} == {
        "service_charges", "common_electricity", "lift_maintenance", "security", "housekeeping"}
    ledgers = {a.system_key: a for a in db.query(Account).filter(Account.society_id == society_id,
                                                                 Account.system_key.isnot(None))}
    for key, code in LINKS.items():
        assert ledgers[key].maintenance_element_id == by_code[code].id, key
    for key in UNLINKED:
        assert ledgers[key].maintenance_element_id is None, key


def test_a_self_registered_society_starts_with_elements_and_links(client, db):
    r = client.post("/api/v1/public/register", json={
        "society_name": "Defaults Heights", "society_code": "DEFH1", "contact_person_name": "A Person",
        "contact_email": "defaults@example.com", "contact_mobile": "9876543210", "city": "Pune", "state": "MH",
        "total_wings": 1, "total_flats": 10, "terms_accepted": True})
    assert r.status_code == 201, r.text
    _assert_defaults(db, r.json()["society_id"] and __import__("uuid").UUID(r.json()["society_id"]))


def test_cleaning_a_societys_data_restores_the_standard_books(client, db):
    a = _seed(db, "DEF2", "Defaults Two")
    _, h = make_superadmin(db)
    ok = client.post(f"{P}/societies/{a.id}/clean-data", json={"confirm": "DEF2"}, headers=h)
    assert ok.status_code == 200, ok.text
    db.expire_all()
    _assert_defaults(db, a.id)
    # cleaning again does not duplicate anything
    assert client.post(f"{P}/societies/{a.id}/clean-data", json={"confirm": "DEF2"}, headers=h).status_code == 200
    db.expire_all()
    assert db.query(MaintenanceElement).filter_by(society_id=a.id).count() == 17


def test_a_society_created_by_the_platform_admin_starts_with_elements_and_links(client, db):
    admin = make_user(db, "adm@defaults3.com", role="Society Admin")
    r = client.post("/api/v1/societies/", json={"name": "Defaults Three"}, headers=admin["headers"])
    assert r.status_code == 201, r.text
    _assert_defaults(db, __import__("uuid").UUID(r.json()["id"]))


# ── Apply standard links to a society that already exists ────────────────────

def _old_society(client, db, tag):
    """A society whose books were made before the defaults: ledgers exist with no links, elements exist."""
    from tests.billing.test_budget_suggestions import _rig
    society, admin, manager, _res = _rig(db, tag)
    assert client.get(f"/api/v1/billing/elements/{society.id}", headers=manager).status_code == 200   # seeds
    seed_society_defaults(db, society.id)                   # and the chart of accounts
    db.commit()
    db.expire_all()
    for a in db.query(Account).filter(Account.society_id == society.id):
        a.maintenance_element_id = None
    db.commit()
    return society, manager


def test_apply_standard_links_links_only_what_has_no_link(client, db):
    society, manager = _old_society(client, db, "al1")
    keep = db.query(Account).filter_by(society_id=society.id, system_key="salaries").one()
    water = db.query(MaintenanceElement).filter_by(society_id=society.id, code="water_charges").one()
    keep.maintenance_element_id = water.id                 # a link the society chose itself
    db.commit()

    r = client.post(f"/api/v1/billing/elements/{society.id}/apply-standard-links", headers=manager)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["linked"]) == len(LINKS) - 1 and body["already_linked"] == 1
    assert {"ledger": "Audit Fees", "element": "Service Charges"} in body["linked"]
    db.expire_all()
    ledgers = {a.system_key: a for a in db.query(Account).filter(Account.society_id == society.id)}
    elements = {e.code: e for e in db.query(MaintenanceElement).filter_by(society_id=society.id)}
    assert ledgers["salaries"].maintenance_element_id == elements["water_charges"].id     # never overridden
    for key, code in LINKS.items():
        if key != "salaries":
            assert ledgers[key].maintenance_element_id == elements[code].id, key
    assert ledgers["bank_charges"].maintenance_element_id is None

    again = client.post(f"/api/v1/billing/elements/{society.id}/apply-standard-links", headers=manager).json()
    assert again["linked"] == [] and again["already_linked"] == len(LINKS)


def test_apply_standard_links_needs_a_manager_and_the_own_society(client, db):
    society, _unscoped = _old_society(client, db, "al2")
    other, _unscoped2 = _old_society(client, db, "al3")
    mine = place_in(db, make_user(db, "mgr@al2own.com", role="Manager"), society)["headers"]
    theirs = place_in(db, make_user(db, "mgr@al3own.com", role="Manager"), other)["headers"]
    resident = place_in(db, make_user(db, "res@al2.com", role="Resident"), society)["headers"]
    url = f"/api/v1/billing/elements/{society.id}/apply-standard-links"
    assert client.post(url, headers=resident).status_code == 403
    assert client.post(url, headers=theirs).status_code == 403          # another society's manager
    assert client.post(url, headers=mine).status_code == 200
