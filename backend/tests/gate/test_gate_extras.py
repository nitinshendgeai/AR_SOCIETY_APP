"""Parcels at the gate; domestic help register, passes and gate entries."""
from datetime import date, timedelta

from app.models.notification import Notification
from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.modules.gate.models.gate import DomesticHelp
from tests.conftest import make_flat, make_society, make_user, make_wing

P = "/api/v1/gate"


def _login(db, email, role, society, flat=None, tenant=False):
    u = make_user(db, email, role=role)
    u["user"].society_id = society.id
    if flat is not None:
        if tenant:
            db.add(Tenant(flat_id=flat.id, user_id=u["user"].id, full_name=email.split("@")[0]))
        else:
            db.add(Resident(flat_id=flat.id, user_id=u["user"].id, full_name=email.split("@")[0],
                            resident_type=ResidentType.OWNER, is_primary=True))
    db.commit()
    return u


def _rig(db, tag):
    society = make_society(db, f"Gate {tag}")
    wing = make_wing(db, society.id, "G")
    f1, f2 = make_flat(db, wing.id, "1"), make_flat(db, wing.id, "2")
    admin = _login(db, f"gate.admin.{tag}@t.com", "Society Admin", society)
    guard = _login(db, f"gate.guard.{tag}@t.com", "Security Staff", society)
    r1 = _login(db, f"gate.r1.{tag}@t.com", "Resident", society, f1)
    r2 = _login(db, f"gate.r2.{tag}@t.com", "Resident", society, f2)
    return society, f1, f2, admin, guard, r1, r2


def _notes(db, user, module):
    return db.query(Notification).filter(Notification.user_id == user["user"].id, Notification.module == module).all()


# ── Parcels ───────────────────────────────────────────────────────────────────

def test_guard_logs_a_parcel_the_flat_is_told_and_it_is_handed_over(client, db):
    society, f1, f2, admin, guard, r1, r2 = _rig(db, "p1")
    base = f"{P}/parcels/society/{society.id}"
    r = client.post(base, json={"flat_id": str(f1.id), "courier": "Amazon", "recipient_name": "Rohan"},
                    headers=guard["headers"])
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["status"] == "at_gate" and r.json()["flat"].endswith("1")
    assert len(_notes(db, r1, "parcel")) == 1 and len(_notes(db, r2, "parcel")) == 0

    # only the flat's own parcels show to a resident; the guard sees all
    assert len(client.get(base, headers=r1["headers"]).json()) == 1
    assert client.get(base, headers=r2["headers"]).json() == []
    assert len(client.get(base + "?status=at_gate", headers=guard["headers"]).json()) == 1
    # another flat cannot touch it
    assert client.post(f"{P}/parcels/{pid}/collect", json={}, headers=r2["headers"]).status_code == 404

    done = client.post(f"{P}/parcels/{pid}/collect", json={"collected_by_name": "Rohan's wife"}, headers=guard["headers"])
    assert done.status_code == 200 and done.json()["status"] == "collected"
    assert done.json()["collected_by_name"] == "Rohan's wife"
    assert client.post(f"{P}/parcels/{pid}/collect", json={}, headers=guard["headers"]).status_code == 409


def test_residents_cannot_log_parcels_and_only_the_gate_returns_them(client, db):
    society, f1, _, admin, guard, r1, _r2 = _rig(db, "p2")
    base = f"{P}/parcels/society/{society.id}"
    assert client.post(base, json={"flat_id": str(f1.id)}, headers=r1["headers"]).status_code == 403
    pid = client.post(base, json={"flat_id": str(f1.id), "description": "Big box"}, headers=guard["headers"]).json()["id"]
    assert client.post(f"{P}/parcels/{pid}/return", json={"note": "Refused"}, headers=r1["headers"]).status_code == 403
    r = client.post(f"{P}/parcels/{pid}/return", json={"note": "Refused"}, headers=guard["headers"])
    assert r.status_code == 200 and r.json()["status"] == "returned" and r.json()["note"] == "Refused"
    # a resident can pick up their own parcel themselves
    pid2 = client.post(base, json={"flat_id": str(f1.id)}, headers=guard["headers"]).json()["id"]
    assert client.post(f"{P}/parcels/{pid2}/collect", json={}, headers=r1["headers"]).json()["status"] == "collected"


def test_a_parcel_for_a_flat_of_another_society_is_refused(client, db):
    society, f1, _, _, guard, _, _ = _rig(db, "p3")
    other, of1, *_ = _rig(db, "p3b")
    r = client.post(f"{P}/parcels/society/{society.id}", json={"flat_id": str(of1.id)}, headers=guard["headers"])
    assert r.status_code == 404


# ── Domestic help ─────────────────────────────────────────────────────────────

def _register(client, who, society, **extra):
    body = {"name": "Sunita Pawar", "mobile": "9876500001", "kind": "maid", **extra}
    return client.post(f"{P}/help/society/{society.id}", json=body, headers=who["headers"])


def test_resident_registers_help_office_issues_a_pass_and_it_prints(client, db):
    society, f1, _, admin, guard, r1, r2 = _rig(db, "h1")
    r = _register(client, r1, society, id_proof="Aadhaar ending 4821")
    assert r.status_code == 201, r.text
    h = r.json()
    assert h["status"] == "pending" and h["pass_no"] is None and [f["flat_id"] for f in h["flats"]] == [str(f1.id)]
    assert len(_notes(db, admin, "domestic_help")) == 1
    # no pass yet: the gate turns them away and no PDF
    assert client.post(f"{P}/help/{h['id']}/scan", headers=guard["headers"]).status_code == 409
    assert client.get(f"{P}/help/{h['id']}/pass", headers=r1["headers"]).status_code == 409

    # only the office approves
    assert client.post(f"{P}/help/{h['id']}/approve", json={}, headers=r1["headers"]).status_code == 403
    a = client.post(f"{P}/help/{h['id']}/approve", json={"police_verified": True}, headers=admin["headers"])
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "active" and a.json()["pass_no"] == "DH-0001" and a.json()["police_verified"]
    assert a.json()["valid_until"] == str(date.today() + timedelta(days=365))
    assert any("DH-0001" in n.body for n in _notes(db, r1, "domestic_help"))

    pdf = client.get(f"{P}/help/{h['id']}/pass", headers=r1["headers"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # another flat's resident cannot see this person
    assert client.get(f"{P}/help/society/{society.id}", headers=r2["headers"]).json() == []
    assert client.get(f"{P}/help/{h['id']}/pass", headers=r2["headers"]).status_code == 404


def test_the_same_person_in_two_flats_is_one_record_with_one_pass(client, db):
    society, f1, f2, admin, guard, r1, r2 = _rig(db, "h2")
    first = _register(client, r1, society).json()
    second = _register(client, r2, society)
    assert second.status_code == 201
    assert second.json()["id"] == first["id"] and len(second.json()["flats"]) == 2
    assert db.query(DomesticHelp).filter(DomesticHelp.society_id == society.id).count() == 1
    # each flat's resident sees them; removing one's own flat leaves the other
    left = client.delete(f"{P}/help/{first['id']}/flats/{f2.id}", headers=r2["headers"])
    assert left.status_code == 200 and [f["flat_id"] for f in left.json()["flats"]] == [str(f1.id)]
    assert client.delete(f"{P}/help/{first['id']}/flats/{f1.id}", headers=r2["headers"]).status_code in (403, 404)


def test_office_registering_gets_an_active_pass_straight_away(client, db):
    society, f1, f2, admin, guard, *_ = _rig(db, "h3")
    r = _register(client, admin, society, kind="driver", flat_ids=[str(f1.id), str(f2.id)], police_verified=True)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active" and r.json()["pass_no"] == "DH-0001" and len(r.json()["flats"]) == 2
    assert _register(client, admin, society, name="Ramesh", mobile="9876500002", kind="cook",
                     flat_ids=[str(f1.id)]).json()["pass_no"] == "DH-0002"


def test_gate_entries_toggle_in_and_out_and_tell_the_flat(client, db):
    society, f1, _, admin, guard, r1, r2 = _rig(db, "h4")
    hid = _register(client, admin, society, flat_ids=[str(f1.id)]).json()["id"]

    a = client.post(f"{P}/help/{hid}/scan", headers=guard["headers"])
    assert a.status_code == 200 and a.json()["direction"] == "in" and a.json()["flats"][0].endswith("1")
    assert [h["id"] for h in client.get(f"{P}/help/society/{society.id}/inside", headers=guard["headers"]).json()] == [hid]
    assert client.get(f"{P}/help/society/{society.id}", headers=guard["headers"]).json()[0]["inside"] is True
    b = client.post(f"{P}/help/{hid}/scan", headers=guard["headers"])
    assert b.json()["direction"] == "out"
    assert client.get(f"{P}/help/society/{society.id}/inside", headers=guard["headers"]).json() == []
    assert [n.body for n in _notes(db, r1, "domestic_help") if "come in" in n.body or "left" in n.body]
    assert _notes(db, r2, "domestic_help") == []

    hist = client.get(f"{P}/help/{hid}/entries", headers=r1["headers"]).json()
    assert len(hist) == 1 and hist[0]["out_at"] is not None
    # residents cannot record entries
    assert client.post(f"{P}/help/{hid}/scan", headers=r1["headers"]).status_code == 403


def test_a_suspended_or_expired_pass_is_refused_at_entry_but_exit_is_always_allowed(client, db):
    society, f1, _, admin, guard, r1, _r2 = _rig(db, "h5")
    hid = _register(client, admin, society, flat_ids=[str(f1.id)]).json()["id"]
    assert client.post(f"{P}/help/{hid}/scan", headers=guard["headers"]).json()["direction"] == "in"
    # suspended while inside: can still leave, cannot come back in
    s = client.post(f"{P}/help/{hid}/status", json={"status": "suspended", "note": "Complaint"}, headers=admin["headers"])
    assert s.status_code == 200 and s.json()["status"] == "suspended"
    assert client.post(f"{P}/help/{hid}/scan", headers=guard["headers"]).json()["direction"] == "out"
    refused = client.post(f"{P}/help/{hid}/scan", headers=guard["headers"])
    assert refused.status_code == 409 and "suspended" in refused.json()["detail"]
    # approving again reactivates; an expired date blocks entry until renewed
    assert client.post(f"{P}/help/{hid}/approve", json={"valid_until": str(date.today() - timedelta(days=1))},
                       headers=admin["headers"]).json()["effective_status"] == "expired"
    assert "expired" in client.post(f"{P}/help/{hid}/scan", headers=guard["headers"]).json()["detail"]
    renewed = client.post(f"{P}/help/{hid}/renew", json={}, headers=admin["headers"])
    assert renewed.status_code == 200 and renewed.json()["effective_status"] == "active"
    assert client.post(f"{P}/help/{hid}/scan", headers=guard["headers"]).json()["direction"] == "in"
    # a residents cannot suspend; search finds by name / pass / mobile
    assert client.post(f"{P}/help/{hid}/status", json={"status": "ended"}, headers=r1["headers"]).status_code == 403
    for q in ("sunita", "DH-0001", "98765"):
        assert len(client.get(f"{P}/help/society/{society.id}?q={q}", headers=guard["headers"]).json()) == 1
    assert client.get(f"{P}/help/society/{society.id}?q=zzz", headers=guard["headers"]).json() == []


def test_a_resident_can_add_help_only_to_their_own_flat(client, db):
    society, f1, f2, admin, guard, r1, r2 = _rig(db, "h6")
    assert _register(client, r1, society, flat_ids=[str(f2.id)]).status_code == 403
    assert _register(client, r1, society, kind="astronaut").status_code == 422
    # office with no flat chosen is told to choose
    assert _register(client, admin, society).status_code == 422
    # a tenant can add help to their own flat too
    t = _login(db, "gate.tenant.h6@t.com", "Tenant", society, f2, tenant=True)
    assert _register(client, t, society, name="Geeta", mobile="9000000009").status_code == 201
