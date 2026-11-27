"""The managing committee register: term, office-bearers, powers and contacts — seen by every member, kept by the
office."""
from datetime import date, timedelta

from app.models.resident import Resident, ResidentType
from tests.governance.test_governance import _resident, _rig

B = "/api/v1/governance/committee"


def _committee(client, society, admin, formed=date(2024, 4, 1)):
    r = client.post(f"{B}/society/{society.id}", json={"formed_on": formed.isoformat()}, headers=admin["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def test_a_committee_gets_a_five_year_term_and_flags_what_is_missing(client, db):
    society, admin, _f1, _f2 = _rig(db, "c1")
    c = _committee(client, society, admin)
    assert c["name"] == "Managing Committee 2024–2029" and c["term_ends_on"] == "2029-03-31"
    w = " ".join(c["warnings"])
    assert "No Chairman" in w and "No Secretary" in w and "No Treasurer" in w and "cheque signatories" in w


def test_office_bearers_from_residents_with_their_contacts_and_powers(client, db):
    society, admin, f1, f2 = _rig(db, "c2")
    r1 = Resident(flat_id=f1.id, full_name="Asha Kulkarni", phone="9800000001", email="asha@t.com",
                  resident_type=ResidentType.OWNER, is_primary=True)
    db.add(r1)
    db.commit()
    c = _committee(client, society, admin)
    r = client.post(f"{B}/{c['id']}/members", json={"resident_id": str(r1.id), "position": "chairman"},
                    headers=admin["headers"])
    assert r.status_code == 201, r.text
    chair = r.json()["members"][0]
    assert chair["full_name"] == "Asha Kulkarni" and chair["phone"] == "9800000001" and chair["flat"] == "W 1"
    assert chair["position_label"] == "Chairman" and chair["cheque_signatory"] and chair["approves_payments"]
    for pos, name in (("secretary", "Ravi"), ("treasurer", "Meena")):
        assert client.post(f"{B}/{c['id']}/members", json={"full_name": name, "position": pos, "phone": "9811111111"},
                           headers=admin["headers"]).status_code == 201
    reg = client.get(f"{B}/society/{society.id}", headers=admin["headers"]).json()["current"]
    assert [m["position"] for m in reg["members"]] == ["chairman", "secretary", "treasurer"]
    assert not any("No " in w or "signatories" in w for w in reg["warnings"])


def test_one_chairman_at_a_time_unless_replaced(client, db):
    society, admin, _f1, _f2 = _rig(db, "c3")
    c = _committee(client, society, admin)
    client.post(f"{B}/{c['id']}/members", json={"full_name": "Old Chair", "position": "chairman"}, headers=admin["headers"])
    r = client.post(f"{B}/{c['id']}/members", json={"full_name": "New Chair", "position": "chairman"},
                    headers=admin["headers"])
    assert r.status_code == 409 and "Old Chair is already Chairman" in r.json()["detail"]
    later = (date(2024, 4, 1) + timedelta(days=400)).isoformat()
    r = client.post(f"{B}/{c['id']}/members", json={"full_name": "New Chair", "position": "chairman", "from_date": later,
                                                    "replace": True}, headers=admin["headers"])
    assert r.status_code == 201
    reg = client.get(f"{B}/society/{society.id}", headers=admin["headers"]).json()["current"]
    assert [m["full_name"] for m in reg["members"] if m["position"] == "chairman"] == ["New Chair"]
    old = next(m for m in reg["former_members"] if m["full_name"] == "Old Chair")
    assert old["to_date"] == (date(2024, 4, 1) + timedelta(days=399)).isoformat()   # left the day before


def test_members_see_it_only_the_office_changes_it(client, db):
    society, admin, f1, _f2 = _rig(db, "c4")
    res = _resident(db, "gov.res.c4@t.com", society, f1)
    c = _committee(client, society, admin)
    assert client.get(f"{B}/society/{society.id}", headers=res["headers"]).json()["current"]["id"] == c["id"]
    assert client.post(f"{B}/{c['id']}/members", json={"full_name": "X"}, headers=res["headers"]).status_code == 403
    other, other_admin, _a, _b = _rig(db, "c4b")
    assert client.get(f"{B}/society/{society.id}", headers=other_admin["headers"]).status_code in (403, 404)
    assert client.post(f"{B}/{c['id']}/members", json={"full_name": "X"},
                       headers=other_admin["headers"]).status_code in (403, 404)


def test_a_new_committee_becomes_current_and_the_old_one_is_kept(client, db):
    society, admin, _f1, _f2 = _rig(db, "c5")
    old = _committee(client, society, admin, formed=date(2019, 4, 1))
    new = _committee(client, society, admin, formed=date(2024, 4, 1))
    reg = client.get(f"{B}/society/{society.id}", headers=admin["headers"]).json()
    assert reg["current"]["id"] == new["id"] and [p["id"] for p in reg["past"]] == [old["id"]]
