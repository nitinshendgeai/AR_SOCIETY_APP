"""A resident invites a guest: approved at once, with a gate code the guard verifies."""
from datetime import datetime, timedelta

from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.modules.visitor.models.visitor import Visitor
from tests.conftest import make_flat, make_society, make_user, make_wing

V = "/api/v1/visitors"


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
    society = make_society(db, f"Pass {tag}")
    wing = make_wing(db, society.id, "P")
    f1, f2 = make_flat(db, wing.id, "1"), make_flat(db, wing.id, "2")
    guard = _login(db, f"pass.guard.{tag}@t.com", "Security Staff", society)
    r1 = _login(db, f"pass.r1.{tag}@t.com", "Resident", society, f1)
    r2 = _login(db, f"pass.r2.{tag}@t.com", "Resident", society, f2)
    return society, f1, f2, guard, r1, r2


def _invite(client, who, mobile="9876500001", **extra):
    return client.post(f"{V}/invite", json={"name": "Asha Guest", "mobile": mobile, **extra}, headers=who["headers"])


def test_a_resident_invites_a_guest_who_is_approved_with_a_code(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "a")
    r = _invite(client, r1, purpose="Dinner")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert len(body["pass_code"]) == 6 and body["pass_code"].isdigit()
    assert body["qr_token"] and body["flat_id"] == str(f1.id)
    assert body["resident_id"] == str(r1["user"].id)


def test_the_guard_verifies_the_code_then_checks_the_guest_in_and_the_code_is_spent(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "b")
    code = _invite(client, r1).json()["pass_code"]

    ok = client.post(f"{V}/verify-pass", json={"code": code}, headers=guard["headers"])
    assert ok.status_code == 200 and ok.json()["name"] == "Asha Guest"

    vid = ok.json()["id"]
    assert client.post(f"{V}/{vid}/checkin", json={}, headers=guard["headers"]).status_code == 200
    again = client.post(f"{V}/verify-pass", json={"code": code}, headers=guard["headers"])
    assert again.status_code == 404                      # used: one answer for wrong, used and expired


def test_a_wrong_or_expired_code_is_not_found(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "c")
    code = _invite(client, r1).json()["pass_code"]
    wrong = "000000" if code != "000000" else "111111"
    assert client.post(f"{V}/verify-pass", json={"code": wrong}, headers=guard["headers"]).status_code == 404

    v = db.query(Visitor).filter(Visitor.pass_code == code).one()
    v.qr_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    assert client.post(f"{V}/verify-pass", json={"code": code}, headers=guard["headers"]).status_code == 404


def test_a_code_only_works_in_its_own_society(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "d")
    other_society = make_society(db, "Pass d other")
    other_guard = _login(db, "pass.guard.d2@t.com", "Security Staff", other_society)
    code = _invite(client, r1).json()["pass_code"]
    assert client.post(f"{V}/verify-pass", json={"code": code}, headers=other_guard["headers"]).status_code == 404


def test_residents_cannot_verify_codes_and_guards_cannot_invite(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "e")
    code = _invite(client, r1).json()["pass_code"]
    assert client.post(f"{V}/verify-pass", json={"code": code}, headers=r2["headers"]).status_code == 403
    assert _invite(client, guard, mobile="9876500002").status_code == 403     # a guard has no flat to invite to


def test_a_resident_can_only_invite_to_their_own_flat(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "f")
    r = _invite(client, r1, flat_id=str(f2.id))
    assert r.status_code == 403


def test_a_tenant_can_invite_too_and_a_live_mobile_cannot_be_invited_twice(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "g")
    tenant = _login(db, "pass.t.g@t.com", "Tenant", society, f1, tenant=True)
    assert _invite(client, tenant, mobile="9876500003").status_code == 201
    dup = _invite(client, r1, mobile="9876500003")
    assert dup.status_code == 409


def test_codes_are_unique_among_live_passes(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "h")
    codes = {_invite(client, r1, mobile=f"98765001{i:02d}").json()["pass_code"] for i in range(8)}
    assert len(codes) == 8


def test_the_expected_arrival_is_kept(client, db):
    society, f1, f2, guard, r1, r2 = _rig(db, "i")
    when = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat()
    body = _invite(client, r1, expected_arrival=when).json()
    assert body["expected_arrival"].startswith(when[:16])
