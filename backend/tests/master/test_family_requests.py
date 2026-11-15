"""A resident asks to add a family member; the Admin or committee approves; only then is the person on the Residents list
(and so in the gym's attendance book)."""
from datetime import date

import pytest

from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.models.wing import Wing
from tests.conftest import make_flat, make_society, make_user, make_wing, place_in

R = "/api/v1/residents"
GYM = "/api/v1/gym"


@pytest.fixture
def rig(db):
    society = make_society(db, "Family Society")
    wing = make_wing(db, society.id, "A")
    flat = make_flat(db, wing.id, "101")
    flat2 = make_flat(db, wing.id, "102")
    owner = make_user(db, "fam-owner@x.test", role="Resident")
    coowner = make_user(db, "fam-coowner@x.test", role="Resident")
    kin = make_user(db, "fam-kin@x.test", role="Resident")
    tenant = make_user(db, "fam-tenant@x.test", role="Tenant")
    admin = make_user(db, "fam-admin@x.test", role="Society Admin")
    committee = make_user(db, "fam-committee@x.test", role="Committee Member")
    manager = make_user(db, "fam-manager@x.test", role="Manager")
    trainer = make_user(db, "fam-trainer@x.test", role="Gym Trainer")
    for u in (owner, coowner, kin, tenant, admin, committee, manager, trainer):
        place_in(db, u, society)
    me = Resident(flat_id=flat.id, user_id=owner["user"].id, full_name="Asha Rao", resident_type=ResidentType.OWNER, is_primary=True)
    co = Resident(flat_id=flat2.id, user_id=coowner["user"].id, full_name="Bela Shah", resident_type=ResidentType.CO_OWNER)
    relative = Resident(flat_id=flat.id, user_id=kin["user"].id, full_name="Vik Rao", resident_type=ResidentType.FAMILY)
    db.add_all([me, co, relative, Tenant(flat_id=flat2.id, user_id=tenant["user"].id, full_name="Rita Tenant")])
    db.commit()
    return {"society": society, "flat": flat, "flat2": flat2, "wing": wing, "owner": owner["headers"],
            "coowner": coowner["headers"], "kin": kin["headers"], "tenant": tenant["headers"], "admin": admin["headers"],
            "committee": committee["headers"], "manager": manager["headers"], "trainer": trainer["headers"], "db": db}


def _ask(client, h, name="Tia Rao", kind="dependent", **extra):
    return client.post(f"{R}/family-requests", json={"full_name": name, "resident_type": kind, **extra}, headers=h)


def _names(client, rig, flat=None):
    r = client.get(R + "/", params={"flat_id": str((flat or rig["flat"]).id), "limit": 100}, headers=rig["admin"])
    assert r.status_code == 200, r.text
    return sorted(x["full_name"] for x in r.json())


def _gym_members(client, rig):
    r = client.get(f"{GYM}/flats/{rig['flat'].id}/members", headers=rig["trainer"])
    assert r.status_code == 200, r.text
    return r.json()


# ── asking ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_an_owner_can_ask_and_nothing_is_added_yet(client, rig):
    r = _ask(client, rig["owner"], phone="9876500011", date_of_birth="2015-04-02")
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["status"], body["full_name"], body["resident_type"], body["flat_display"]) == ("pending", "Tia Rao", "dependent", "A-101")
    assert body["requester_name"] and body["rejection_reason"] is None
    assert "Tia Rao" not in _names(client, rig)                                       # not on the Residents list
    assert "Tia Rao" not in [m["name"] for m in _gym_members(client, rig)["members"]]  # so not in the gym's book


def test_the_gym_desk_is_told_who_is_waiting_for_approval(client, rig):
    _ask(client, rig["owner"], name="Tia Rao")
    _ask(client, rig["owner"], name="Neel Rao", kind="family")
    body = _gym_members(client, rig)
    assert body["waiting_for_approval"] == ["Tia Rao", "Neel Rao"]
    assert [m["name"] for m in body["members"]] == ["Asha Rao", "Vik Rao"]


def test_a_request_is_listed_for_the_resident_who_made_it(client, rig):
    _ask(client, rig["owner"])
    mine = client.get(f"{R}/family-requests/mine", headers=rig["owner"]).json()
    assert [(m["full_name"], m["status"]) for m in mine] == [("Tia Rao", "pending")]
    assert client.get(f"{R}/family-requests/mine", headers=rig["coowner"]).json() == []


def test_only_family_or_dependent_can_be_asked_for(client, rig):
    for kind in ("owner", "co_owner", "tenant", ""):
        assert _ask(client, rig["owner"], kind=kind).status_code == 422, kind


def test_bad_details_are_refused(client, rig):
    assert _ask(client, rig["owner"], name="x").status_code == 422
    assert _ask(client, rig["owner"], name="   ").status_code == 422
    assert _ask(client, rig["owner"], phone="12345").status_code == 422
    assert _ask(client, rig["owner"], date_of_birth="2999-01-01").status_code == 422


def test_the_same_person_cannot_be_asked_twice_or_if_already_listed(client, rig):
    assert _ask(client, rig["owner"], name="Tia Rao").status_code == 201
    assert _ask(client, rig["owner"], name="  tia   RAO ").status_code == 409          # waiting already, ignoring case and spaces
    assert _ask(client, rig["owner"], name="vik rao", kind="family").status_code == 409  # already on the list


def test_only_so_many_can_wait_at_once(client, rig):
    for i in range(10):
        assert _ask(client, rig["owner"], name=f"Person Number{chr(65 + i)}").status_code == 201
    assert _ask(client, rig["owner"], name="One Toomany").status_code == 409


def test_only_an_owner_or_co_owner_may_ask(client, rig):
    assert _ask(client, rig["kin"]).status_code == 403            # a family member of the flat
    assert _ask(client, rig["tenant"]).status_code == 403
    assert _ask(client, rig["trainer"]).status_code == 403
    assert _ask(client, rig["coowner"], name="Neel Shah", kind="family").status_code == 201   # a co-owner may (flat 102)


def test_a_login_is_needed(client, rig):
    assert client.post(f"{R}/family-requests", json={"full_name": "Tia Rao", "resident_type": "family"}).status_code in (401, 403)
    assert client.get(f"{R}/family-requests/mine").status_code in (401, 403)


def test_an_owner_of_two_flats_must_say_which(client, db, rig):
    owner_user_id = db.query(Resident).filter_by(full_name="Asha Rao").one().user_id
    db.add(Resident(flat_id=rig["flat2"].id, user_id=owner_user_id, full_name="Asha Rao", resident_type=ResidentType.OWNER))
    db.commit()
    assert _ask(client, rig["owner"]).status_code == 422
    r = _ask(client, rig["owner"], flat_id=str(rig["flat2"].id))
    assert r.status_code == 201 and r.json()["flat_display"] == "A-102"
    far = make_flat(db, rig["wing"].id, "999")
    assert _ask(client, rig["owner"], name="Other Person", flat_id=str(far.id)).status_code == 404       # not their flat


# ── approving ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_admin_sees_the_request_and_approving_adds_the_person(client, rig):
    req = _ask(client, rig["owner"], phone="9876500011", date_of_birth="2015-04-02").json()
    pending = client.get(f"{R}/family-requests/pending", headers=rig["admin"]).json()
    assert [(p["full_name"], p["flat_display"]) for p in pending] == [("Tia Rao", "A-101")]

    r = client.post(f"{R}/family-requests/{req['id']}/approve", headers=rig["admin"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    added = rig["db"].query(Resident).filter_by(full_name="Tia Rao").one()
    assert (added.flat_id, added.resident_type, added.is_primary, added.phone, added.date_of_birth, added.is_active) == (
        rig["flat"].id, ResidentType.DEPENDENT, False, "9876500011", date(2015, 4, 2), True)
    assert added.user_id is None                                                      # approval does not make an app login
    assert "Tia Rao" in _names(client, rig)
    gym = _gym_members(client, rig)
    assert "Tia Rao" in [m["name"] for m in gym["members"]] and gym["waiting_for_approval"] == []
    assert client.get(f"{R}/family-requests/pending", headers=rig["admin"]).json() == []
    assert client.get(f"{R}/family-requests/mine", headers=rig["owner"]).json()[0]["status"] == "approved"


def test_a_committee_member_can_approve_too(client, rig):
    req = _ask(client, rig["owner"]).json()
    assert client.post(f"{R}/family-requests/{req['id']}/approve", headers=rig["committee"]).status_code == 200


def test_rejecting_needs_a_reason_and_adds_nobody(client, rig):
    req = _ask(client, rig["owner"]).json()
    assert client.post(f"{R}/family-requests/{req['id']}/reject", json={"reason": "   "}, headers=rig["admin"]).status_code == 422
    r = client.post(f"{R}/family-requests/{req['id']}/reject", json={"reason": "Please add their ID first"}, headers=rig["admin"])
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert "Tia Rao" not in _names(client, rig)
    mine = client.get(f"{R}/family-requests/mine", headers=rig["owner"]).json()[0]
    assert (mine["status"], mine["rejection_reason"]) == ("rejected", "Please add their ID first")
    assert _gym_members(client, rig)["waiting_for_approval"] == []
    assert _ask(client, rig["owner"]).status_code == 201                              # may ask again, with the right details


def test_a_request_can_be_reviewed_only_once(client, rig):
    req = _ask(client, rig["owner"]).json()
    assert client.post(f"{R}/family-requests/{req['id']}/approve", headers=rig["admin"]).status_code == 200
    assert client.post(f"{R}/family-requests/{req['id']}/approve", headers=rig["admin"]).status_code == 409
    assert client.post(f"{R}/family-requests/{req['id']}/reject", json={"reason": "late"}, headers=rig["admin"]).status_code == 409
    assert [r.full_name for r in rig["db"].query(Resident).filter_by(full_name="Tia Rao")] == ["Tia Rao"]    # added once


def test_approving_a_name_the_office_has_since_added_is_refused(client, rig, db):
    req = _ask(client, rig["owner"]).json()
    db.add(Resident(flat_id=rig["flat"].id, full_name="Tia Rao", resident_type=ResidentType.FAMILY))   # the office added her directly
    db.commit()
    assert client.post(f"{R}/family-requests/{req['id']}/approve", headers=rig["admin"]).status_code == 409


def test_only_the_admin_or_committee_can_review(client, rig):
    req = _ask(client, rig["owner"]).json()
    for who in ("owner", "manager", "kin", "trainer", "tenant"):
        h = rig[who]
        assert client.get(f"{R}/family-requests/pending", headers=h).status_code == 403, who
        assert client.post(f"{R}/family-requests/{req['id']}/approve", headers=h).status_code == 403, who
        assert client.post(f"{R}/family-requests/{req['id']}/reject", json={"reason": "no"}, headers=h).status_code == 403, who
    assert "Tia Rao" not in _names(client, rig)


def test_another_society_cannot_see_or_approve(client, db, rig):
    req = _ask(client, rig["owner"]).json()
    other = make_society(db, "Other Family Society")
    far_admin = make_user(db, "fam-far-admin@x.test", role="Society Admin")
    place_in(db, far_admin, other)
    assert client.get(f"{R}/family-requests/pending", headers=far_admin["headers"]).json() == []
    assert client.post(f"{R}/family-requests/{req['id']}/approve", headers=far_admin["headers"]).status_code == 404
    assert client.post(f"{R}/family-requests/{req['id']}/reject", json={"reason": "no"}, headers=far_admin["headers"]).status_code == 404
    assert client.get(f"{R}/family-requests/pending", headers=rig["admin"]).json()[0]["full_name"] == "Tia Rao"   # still waiting


def test_the_dashboard_counts_family_requests_with_the_other_pending_changes(client, db, rig):
    from app.modules.dashboard.services.dashboard_service import DashboardService

    def waiting():
        items = DashboardService(db)._attention(rig["society"].id, date.today())
        return next((i["count"] for i in items if i["key"] == "resident_changes"), 0)

    assert waiting() == 0
    req = _ask(client, rig["owner"]).json()
    _ask(client, rig["owner"], name="Neel Rao", kind="family")
    assert waiting() == 2
    client.post(f"{R}/family-requests/{req['id']}/approve", headers=rig["admin"])
    assert waiting() == 1
