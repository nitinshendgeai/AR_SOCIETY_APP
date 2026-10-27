"""A new society, and one whose data was cleaned, starts with the standard maintenance elements and every standard
expense ledger linked to the element it pays for - without anyone opening the billing screens first."""
from app.modules.accounts.models.accounts import Account
from app.modules.billing.models.billing import MaintenanceElement
from tests.conftest import make_user
from tests.platform_admin.test_society_purge import P, _seed, make_superadmin

LINKS = {
    "security_charges": "security", "cctv_maintenance": "security", "housekeeping": "housekeeping",
    "garden": "housekeeping", "pest_control": "housekeeping", "lift_maintenance": "lift_maintenance",
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
    assert len(elements) == 14
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
    assert db.query(MaintenanceElement).filter_by(society_id=a.id).count() == 14


def test_a_society_created_by_the_platform_admin_starts_with_elements_and_links(client, db):
    admin = make_user(db, "adm@defaults3.com", role="Society Admin")
    r = client.post("/api/v1/societies/", json={"name": "Defaults Three"}, headers=admin["headers"])
    assert r.status_code == 201, r.text
    _assert_defaults(db, __import__("uuid").UUID(r.json()["id"]))
