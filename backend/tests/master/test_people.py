"""Residents, tenants and vehicles: what the forms send is checked, tidied and
stored as typed; fields can be cleared; nothing crosses a society or a flat."""
import pytest
from uuid import UUID as _UUID

from tests.conftest import make_user, make_society, make_wing, make_flat


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _UUID(str(society_id))
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def rig(db):
    society = make_society(db, "People Society")
    admin = make_user(db, "padm@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing P1")
    flat = make_flat(db, wing.id, "P-101")
    flat2 = make_flat(db, wing.id, "P-102")

    other = make_society(db, "Other People Society")
    other_admin = make_user(db, "poth@test.com", role="Society Admin")
    _set_society(db, other_admin["user"], other.id)
    other_wing = make_wing(db, other.id, "Wing O1")
    other_flat = make_flat(db, other_wing.id, "O-101")
    return {"society": society, "admin": admin, "h": admin["headers"], "flat": flat, "flat2": flat2,
            "other_admin": other_admin, "other_flat": other_flat}


def _resident(client, rig, **kw):
    body = {"flat_id": str(rig["flat"].id), "full_name": "Asha Rao", **kw}
    return client.post("/api/v1/residents/", json=body, headers=rig["h"])


def _tenant(client, rig, **kw):
    body = {"flat_id": str(rig["flat"].id), "full_name": "Ravi Nair", **kw}
    return client.post("/api/v1/tenants/", json=body, headers=rig["h"])


def _vehicle(client, rig, number="MH12AB1234", **kw):
    body = {"society_id": str(rig["society"].id), "vehicle_number": number, **kw}
    return client.post("/api/v1/vehicles/", json=body, headers=rig["h"])


# ── Residents ────────────────────────────────────────────────────────────────

def test_resident_name_is_tidied_and_never_blank(client, rig):
    r = _resident(client, rig, full_name="  Asha   Rao ")
    assert r.status_code == 201, r.text
    assert r.json()["full_name"] == "Asha Rao"
    assert _resident(client, rig, full_name="   ").status_code == 422
    assert _resident(client, rig, full_name="x" * 256).status_code == 422
    rid = r.json()["id"]
    assert client.patch(f"/api/v1/residents/{rid}", json={"full_name": " "}, headers=rig["h"]).status_code == 422


@pytest.mark.parametrize("bad", ["not-an-email", "a@b", "two words@x.com", "@x.com"])
def test_resident_and_tenant_email_must_be_an_email(client, rig, bad):
    assert _resident(client, rig, email=bad).status_code == 422
    assert _tenant(client, rig, email=bad).status_code == 422


def test_blank_email_and_phone_are_stored_as_nothing(client, rig):
    r = _resident(client, rig, email="  ", phone=" ")
    assert r.status_code == 201, r.text
    assert r.json()["email"] is None and r.json()["phone"] is None
    r = _resident(client, rig, email=" Asha@Example.COM ")
    assert r.json()["email"] == "asha@example.com"


def test_emergency_phone_is_checked(client, rig):
    assert _resident(client, rig, emergency_contact_phone="abc").status_code == 422
    assert _tenant(client, rig, emergency_contact_phone="12").status_code == 422
    assert _resident(client, rig, emergency_contact_phone="98765 43210").status_code == 201


def test_overlong_values_are_refused_not_500(client, rig):
    assert _resident(client, rig, id_proof_number="1" * 101).status_code == 422
    assert _resident(client, rig, id_proof_type="x" * 51).status_code == 422
    assert _resident(client, rig, kyc_doc_url="http://x/" + "a" * 500).status_code == 422
    assert _tenant(client, rig, id_proof_number="1" * 101).status_code == 422
    assert _tenant(client, rig, emergency_contact_name="n" * 256).status_code == 422


def test_date_of_birth_cannot_be_in_the_future(client, rig):
    assert _resident(client, rig, date_of_birth="2999-01-01").status_code == 422
    assert _resident(client, rig, date_of_birth="1850-01-01").status_code == 422
    assert _resident(client, rig, date_of_birth="1980-05-01").status_code == 201


def test_user_link_must_be_in_the_same_society(client, db, rig):
    outsider = rig["other_admin"]["user"]
    r = _resident(client, rig, user_id=str(outsider.id))
    assert r.status_code in (404, 422), r.text
    r = _tenant(client, rig, user_id=str(outsider.id))
    assert r.status_code in (404, 422), r.text
    r = _resident(client, rig, user_id=str(rig["admin"]["user"].id), phone="9876543210")
    assert r.status_code == 201, r.text


def test_resident_fields_can_be_cleared(client, rig):
    r = _resident(client, rig, phone="9876543210", email="a@b.com", id_proof_type="Aadhaar",
                  id_proof_number="1234", emergency_contact_name="Raj", emergency_contact_phone="9876543211",
                  date_of_birth="1980-01-01")
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    cleared = {k: None for k in ("phone", "email", "id_proof_type", "id_proof_number", "emergency_contact_name",
                                 "emergency_contact_phone", "date_of_birth")}
    p = client.patch(f"/api/v1/residents/{rid}", json=cleared, headers=rig["h"])
    assert p.status_code == 200, p.text
    assert all(p.json()[k] is None for k in cleared), p.json()
    # What isn't sent is left alone; required fields stay
    assert p.json()["full_name"] == "Asha Rao"
    p = client.patch(f"/api/v1/residents/{rid}", json={"full_name": None, "is_primary": None}, headers=rig["h"])
    assert p.status_code == 200 and p.json()["full_name"] == "Asha Rao" and p.json()["is_primary"] is False


def test_tenant_fields_can_be_cleared(client, rig):
    t = _tenant(client, rig, phone="9876543210", email="t@b.com", remarks="Hi", emergency_contact_name="Raj")
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    p = client.patch(f"/api/v1/tenants/{tid}", json={"phone": None, "email": None, "remarks": None,
                                                     "emergency_contact_name": None}, headers=rig["h"])
    assert p.status_code == 200, p.text
    assert p.json()["phone"] is None and p.json()["email"] is None and p.json()["remarks"] is None
    assert p.json()["emergency_contact_name"] is None and p.json()["full_name"] == "Ravi Nair"


def test_resident_user_link_on_update_is_checked(client, rig):
    rid = _resident(client, rig).json()["id"]
    p = client.patch(f"/api/v1/residents/{rid}", json={"user_id": str(rig["other_admin"]["user"].id)},
                     headers=rig["h"])
    assert p.status_code in (404, 422), p.text


# ── Tenants ──────────────────────────────────────────────────────────────────

def test_tenant_money_and_name_limits(client, rig):
    assert _tenant(client, rig, monthly_rent="99999999999.00").status_code == 422
    assert _tenant(client, rig, security_deposit="-1").status_code == 422
    assert _tenant(client, rig, full_name="  ").status_code == 422
    t = _tenant(client, rig, monthly_rent="25000", security_deposit="75000", full_name=" Ravi  Nair ")
    assert t.status_code == 201, t.text
    assert t.json()["full_name"] == "Ravi Nair"


def test_agreement_dates_need_a_sane_range(client, rig):
    assert _tenant(client, rig, agreement_start_date="0001-01-01", agreement_end_date="0002-01-01").status_code == 422
    assert _tenant(client, rig, agreement_start_date="2026-01-01", agreement_end_date="2026-12-31").status_code == 201


# ── Moving in and out ────────────────────────────────────────────────────────

def test_move_out_cannot_precede_move_in(client, rig):
    h = rig["h"]
    rid = _resident(client, rig, move_in_date="2026-06-01").json()["id"]
    r = client.post("/api/v1/occupancy/resident/move-out",
                    json={"flat_id": str(rig["flat"].id), "resident_id": rid, "move_out_date": "2026-05-01"}, headers=h)
    assert r.status_code == 422, r.text
    r = client.post("/api/v1/occupancy/resident/move-out",
                    json={"flat_id": str(rig["flat2"].id), "resident_id": rid, "move_out_date": "2026-07-01"}, headers=h)
    assert r.status_code == 404
    r = client.post("/api/v1/occupancy/resident/move-out",
                    json={"flat_id": str(rig["flat"].id), "resident_id": rid, "move_out_date": "2026-07-01"}, headers=h)
    assert r.status_code == 200, r.text

    tid = _tenant(client, rig, full_name="Tina", move_in_date="2026-06-01").json()["id"]
    r = client.post("/api/v1/occupancy/tenant/move-out",
                    json={"flat_id": str(rig["flat"].id), "tenant_id": tid, "move_out_date": "2026-05-01"}, headers=h)
    assert r.status_code == 422, r.text


# ── Vehicles ─────────────────────────────────────────────────────────────────

def test_vehicle_number_is_checked_and_normalised(client, rig):
    assert _vehicle(client, rig, number="  ").status_code == 422
    assert _vehicle(client, rig, number="A").status_code == 422
    assert _vehicle(client, rig, number="MH 12 @@ 12!").status_code == 422
    assert _vehicle(client, rig, number="X" * 31).status_code == 422
    r = _vehicle(client, rig, number="mh-12 ab 1234")
    assert r.status_code == 201, r.text
    assert r.json()["vehicle_number"] == "MH12AB1234"
    assert _vehicle(client, rig, number="MH12AB1234").status_code == 409


def test_vehicle_year_expiry_and_lengths(client, rig):
    assert _vehicle(client, rig, "MH01AA0001", year="abcd").status_code == 422
    assert _vehicle(client, rig, "MH01AA0002", year="1850").status_code == 422
    assert _vehicle(client, rig, "MH01AA0003", year="2999").status_code == 422
    assert _vehicle(client, rig, "MH01AA0004", insurance_expiry="31/12/2026").status_code == 422
    assert _vehicle(client, rig, "MH01AA0005", insurance_expiry="2026-13-45").status_code == 422
    assert _vehicle(client, rig, "MH01AA0006", make="m" * 101).status_code == 422
    assert _vehicle(client, rig, "MH01AA0007", parking_slot="p" * 21).status_code == 422
    assert _vehicle(client, rig, "MH01AA0008", rfid_tag="r" * 101).status_code == 422
    r = _vehicle(client, rig, "MH01AA0009", year="2021", insurance_expiry="2027-03-31", make=" Honda ",
                 color="  ", parking_slot=" B-12 ")
    assert r.status_code == 201, r.text
    j = r.json()
    assert (j["year"], j["insurance_expiry"], j["make"], j["color"], j["parking_slot"]) == (
        "2021", "2027-03-31", "Honda", None, "B-12")


def test_rfid_tag_is_unique_with_a_clear_message(client, rig):
    assert _vehicle(client, rig, "MH02AA0001", rfid_tag="TAG-1").status_code == 201
    r = _vehicle(client, rig, "MH02AA0002", rfid_tag="TAG-1")
    assert r.status_code == 409, r.text
    assert "RFID" in r.json()["detail"]
    v = _vehicle(client, rig, "MH02AA0003").json()
    p = client.patch(f"/api/v1/vehicles/{v['id']}", json={"rfid_tag": "TAG-1"}, headers=rig["h"])
    assert p.status_code == 409, p.text


def test_vehicle_fields_can_be_cleared(client, rig):
    v = _vehicle(client, rig, "MH03AA0001", make="Honda", model="City", color="Red", parking_slot="B-1",
                 rfid_tag="T-9", year="2020", remarks="Hello").json()
    p = client.patch(f"/api/v1/vehicles/{v['id']}", json={"make": None, "color": None, "parking_slot": None,
                                                          "rfid_tag": None, "year": None}, headers=rig["h"])
    assert p.status_code == 200, p.text
    j = p.json()
    assert j["make"] is None and j["color"] is None and j["parking_slot"] is None and j["rfid_tag"] is None
    assert j["year"] is None and j["model"] == "City"
    # The free RFID tag can be used again
    assert _vehicle(client, rig, "MH03AA0002", rfid_tag="T-9").status_code == 201


def test_vehicle_update_validates(client, rig):
    v = _vehicle(client, rig, "MH04AA0001").json()
    h = rig["h"]
    assert client.patch(f"/api/v1/vehicles/{v['id']}", json={"insurance_expiry": "tomorrow"}, headers=h).status_code == 422
    assert client.patch(f"/api/v1/vehicles/{v['id']}", json={"year": "20x1"}, headers=h).status_code == 422
    assert client.patch(f"/api/v1/vehicles/{v['id']}", json={"color": "c" * 51}, headers=h).status_code == 422
    assert client.patch(f"/api/v1/vehicles/{v['id']}", json={"year": "2019", "insurance_expiry": "2027-01-01"},
                        headers=h).json()["year"] == "2019"


def test_deregistered_number_can_be_registered_again(client, rig):
    v = _vehicle(client, rig, "MH05AA0001", rfid_tag="T-5").json()
    assert client.delete(f"/api/v1/vehicles/{v['id']}", headers=rig["h"]).status_code == 204
    r = _vehicle(client, rig, "MH05AA0001", rfid_tag="T-5")
    assert r.status_code == 201, r.text


def test_vehicle_must_sit_on_a_flat_of_the_society(client, rig):
    r = _vehicle(client, rig, "MH06AA0001", flat_id=str(rig["other_flat"].id))
    assert r.status_code == 404


def test_residents_see_and_register_only_their_own_flat(client, db, rig):
    resident_user = make_user(db, "pres@test.com", role="Resident")
    _set_society(db, resident_user["user"], rig["society"].id)
    rid = _resident(client, rig, user_id=str(resident_user["user"].id), phone="9876543210").json()["id"]
    rh = resident_user["headers"]
    mine = _vehicle(client, rig, "MH07AA0001", flat_id=str(rig["flat"].id), resident_id=rid).json()
    other = _vehicle(client, rig, "MH07AA0002", flat_id=str(rig["flat2"].id)).json()

    # Registers on own flat; not on someone else's, nor with no flat
    own = client.post("/api/v1/vehicles/", json={"society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
                                                 "vehicle_number": "MH07AA0003"}, headers=rh)
    assert own.status_code == 201, own.text
    r = client.post("/api/v1/vehicles/", json={"society_id": str(rig["society"].id), "flat_id": str(rig["flat2"].id),
                                               "vehicle_number": "MH07AA0004"}, headers=rh)
    assert r.status_code == 403, r.text
    r = client.post("/api/v1/vehicles/", json={"society_id": str(rig["society"].id), "vehicle_number": "MH07AA0005"},
                    headers=rh)
    assert r.status_code == 403, r.text

    # Sees own flat's vehicles only
    listed = client.get(f"/api/v1/vehicles/society/{rig['society'].id}", headers=rh).json()
    assert {v["vehicle_number"] for v in listed} == {"MH07AA0001", "MH07AA0003"}
    assert client.get(f"/api/v1/vehicles/{other['id']}", headers=rh).status_code == 404
    assert client.get(f"/api/v1/vehicles/{mine['id']}", headers=rh).status_code == 200
    assert client.get(f"/api/v1/vehicles/flat/{rig['flat2'].id}", headers=rh).json() == []

    # Admin sees everything
    assert len(client.get(f"/api/v1/vehicles/society/{rig['society'].id}", headers=rig["h"]).json()) == 3


def test_self_service_edit_request_is_validated_like_the_form(client, db, rig):
    user = make_user(db, "pself@test.com", role="Resident")
    _set_society(db, user["user"], rig["society"].id)
    assert _resident(client, rig, user_id=str(user["user"].id), phone="9876543210").status_code == 201
    h = user["headers"]
    for bad in ({"phone": "abc"}, {"email": "nope"}, {"full_name": "  "}, {"date_of_birth": "2999-01-01"},
                {"emergency_contact_phone": "1"}):
        assert client.post("/api/v1/residents/edit-requests", json=bad, headers=h).status_code == 422, bad
    ok = client.post("/api/v1/residents/edit-requests", json={"email": " New@Example.com "}, headers=h)
    assert ok.status_code == 201 and ok.json()["changes"]["email"] == "new@example.com"
