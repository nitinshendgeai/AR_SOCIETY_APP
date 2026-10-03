"""Visitors: what the gate form sends is checked and tidied; a visitor, gate or
list never crosses a society; only the flat's own people (or the committee)
answer for a visitor."""
import pytest
from uuid import UUID as _UUID

from tests.conftest import make_user, make_society, make_wing, make_flat

V = "/api/v1/visitors"


def _in(db, user, society):
    user["user"].society_id = _UUID(str(society.id))
    db.commit()
    return user


@pytest.fixture
def rig(db):
    society = make_society(db, "Gate Society")
    wing = make_wing(db, society.id, "Wing G")
    flat = make_flat(db, wing.id, "G-101")
    flat2 = make_flat(db, wing.id, "G-102")
    admin = _in(db, make_user(db, "gadm@v.com", role="Society Admin"), society)
    guard = _in(db, make_user(db, "ggrd@v.com", role="Security Staff"), society)
    res = _in(db, make_user(db, "gres@v.com", role="Resident"), society)
    res2 = _in(db, make_user(db, "gres2@v.com", role="Resident"), society)
    from app.models.resident import Resident, ResidentType
    db.add_all([Resident(flat_id=flat.id, user_id=res["user"].id, full_name="Own", resident_type=ResidentType.OWNER,
                         is_primary=True),
                Resident(flat_id=flat2.id, user_id=res2["user"].id, full_name="Other",
                         resident_type=ResidentType.OWNER, is_primary=True)])
    db.commit()

    other = make_society(db, "Other Gate Society")
    ow = make_wing(db, other.id, "Wing X")
    oflat = make_flat(db, ow.id, "X-1")
    oadmin = _in(db, make_user(db, "oadm@v.com", role="Society Admin"), other)
    oguard = _in(db, make_user(db, "ogrd@v.com", role="Security Staff"), other)
    return dict(society=society, flat=flat, flat2=flat2, admin=admin, guard=guard, res=res, res2=res2,
                other=other, oflat=oflat, oadmin=oadmin, oguard=oguard)


def _body(rig, **kw):
    return {"name": "Ramesh Kumar", "mobile": "9876501234", "society_id": str(rig["society"].id),
            "flat_id": str(rig["flat"].id), **kw}


def _log(client, rig, who="guard", **kw):
    return client.post(f"{V}/", json=_body(rig, **kw), headers=rig[who]["headers"])


def test_visitor_fields_are_checked_and_tidied(client, rig):
    assert _log(client, rig, name="   ").status_code == 422
    assert _log(client, rig, name="n" * 256).status_code == 422
    assert _log(client, rig, mobile="12+34").status_code == 422
    assert _log(client, rig, mobile="123").status_code == 422
    assert _log(client, rig, mobile="9" * 16).status_code == 422
    assert _log(client, rig, purpose="p" * 501).status_code == 422
    assert _log(client, rig, vehicle={"vehicle_number": "@@"}).status_code == 422
    assert _log(client, rig, vehicle={"vehicle_number": "m" * 2}).status_code == 422
    assert _log(client, rig, vehicle={"vehicle_model": "m" * 101}).status_code == 422
    r = _log(client, rig, name="  Ramesh   Kumar ", mobile="+91 98765-01234", purpose="  ", vehicle={
        "vehicle_number": "mh-12 ab 1234", "vehicle_type": "car", "vehicle_color": " "})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["name"] == "Ramesh Kumar" and j["mobile"] == "9876501234" and j["purpose"] is None
    assert j["vehicle"]["vehicle_number"] == "MH12AB1234" and j["vehicle"]["vehicle_color"] is None
    # The same person typed another way is the same active entry
    assert _log(client, rig, mobile="09876501234").status_code == 409


def test_reject_needs_a_real_reason(client, rig):
    vid = _log(client, rig).json()["id"]
    h = rig["res"]["headers"]
    assert client.post(f"{V}/{vid}/reject", json={"reason": "  "}, headers=h).status_code == 422
    assert client.post(f"{V}/{vid}/reject", json={"reason": "r" * 1001}, headers=h).status_code == 422
    r = client.post(f"{V}/{vid}/reject", json={"reason": " Not expected "}, headers=h)
    assert r.status_code == 200 and r.json()["rejection_reason"] == "Not expected"


def test_only_the_flats_people_or_the_committee_decide(client, rig):
    vid = _log(client, rig).json()["id"]
    # Another flat's resident doesn't even see it; a guard sees it but can't decide
    assert client.post(f"{V}/{vid}/approve", json={}, headers=rig["res2"]["headers"]).status_code == 404
    assert client.post(f"{V}/{vid}/reject", json={"reason": "no"}, headers=rig["res2"]["headers"]).status_code == 404
    assert client.post(f"{V}/{vid}/approve", json={}, headers=rig["guard"]["headers"]).status_code == 403
    # Another society's admin doesn't even see it
    assert client.post(f"{V}/{vid}/approve", json={}, headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.post(f"{V}/{vid}/approve", json={}, headers=rig["res"]["headers"]).status_code == 200
    # The committee can answer for any flat
    v2 = _log(client, rig, mobile="9876501299", flat_id=str(rig["flat2"].id)).json()["id"]
    assert client.post(f"{V}/{v2}/approve", json={}, headers=rig["admin"]["headers"]).status_code == 200


def test_nothing_crosses_a_society(client, rig):
    vid = _log(client, rig).json()["id"]
    oh, og = rig["oadmin"]["headers"], rig["oguard"]["headers"]
    assert client.get(f"{V}/{vid}", headers=oh).status_code == 404
    assert client.get(f"{V}/society/{rig['society'].id}", headers=og).status_code == 403
    assert client.get(f"{V}/society/{rig['society'].id}/inside", headers=og).status_code == 403
    assert client.get(f"{V}/gates/{rig['society'].id}", headers=oh).status_code == 403
    assert client.post(f"{V}/{vid}/checkin", json={}, headers=og).status_code == 404
    assert client.post(f"{V}/{vid}/checkout", json={}, headers=og).status_code == 404
    # Logging at, or for a flat in, another society
    assert client.post(f"{V}/", json={**_body(rig), "society_id": str(rig["other"].id)}, headers=rig["guard"]["headers"]
                       ).status_code == 403
    assert client.post(f"{V}/", json={**_body(rig, mobile="9876500001"), "flat_id": str(rig["oflat"].id)},
                       headers=rig["guard"]["headers"]).status_code == 422
    gate = client.post(f"{V}/gates", json={"society_id": str(rig["other"].id), "name": "Z"}, headers=rig["admin"]["headers"])
    assert gate.status_code == 403


def test_gate_belongs_to_the_society_and_is_checked(client, rig):
    h = rig["admin"]["headers"]
    sid = str(rig["society"].id)
    assert client.post(f"{V}/gates", json={"society_id": sid, "name": "  "}, headers=h).status_code == 422
    assert client.post(f"{V}/gates", json={"society_id": sid, "name": "g" * 101}, headers=h).status_code == 422
    g = client.post(f"{V}/gates", json={"society_id": sid, "name": " Main  Gate "}, headers=h)
    assert g.status_code == 201 and g.json()["name"] == "Main Gate"
    assert client.post(f"{V}/gates", json={"society_id": sid, "name": "main gate"}, headers=h).status_code == 409
    og = client.post(f"{V}/gates", json={"society_id": str(rig["other"].id), "name": "Other Gate"},
                     headers=rig["oadmin"]["headers"]).json()
    vid = _log(client, rig).json()["id"]
    # Another society's gate can't be used
    assert client.post(f"{V}/{vid}/checkin", json={"gate_id": og["id"]}, headers=rig["guard"]["headers"]).status_code == 422
    assert client.post(f"{V}/{vid}/checkin", json={"gate_id": g.json()["id"]}, headers=rig["guard"]["headers"]).status_code == 200


def test_residents_see_only_their_flats_visitors(client, rig):
    mine = _log(client, rig).json()["id"]
    theirs = _log(client, rig, mobile="9876500002", flat_id=str(rig["flat2"].id)).json()["id"]
    h = rig["res"]["headers"]
    assert client.get(f"{V}/{mine}", headers=h).status_code == 200
    assert client.get(f"{V}/{theirs}", headers=h).status_code == 404
    assert client.get(f"{V}/{theirs}", headers=rig["guard"]["headers"]).status_code == 200
    # A resident can't browse the society log
    assert client.get(f"{V}/society/{rig['society'].id}", headers=h).status_code == 403


def test_a_named_resident_must_be_in_the_society(client, rig):
    r = _log(client, rig, resident_id=str(rig["oadmin"]["user"].id))
    assert r.status_code == 422, r.text
    r = _log(client, rig, mobile="9876500003", resident_id=str(rig["res"]["user"].id))
    assert r.status_code == 201


def test_list_paging_is_bounded(client, rig):
    g = rig["guard"]["headers"]
    assert client.get(f"{V}/society/{rig['society'].id}?limit=100000", headers=g).status_code == 422
    assert client.get(f"{V}/society/{rig['society'].id}?skip=-1", headers=g).status_code == 422
    assert client.get(f"{V}/society/{rig['society'].id}?limit=10", headers=g).status_code == 200
