"""Phase 1 — tenant isolation and role checks found missing by the audit (see docs/audit/PHASE_1_SECURITY_AUDIT.md).

Each test names the defect it pins. Where the behaviour was already right the test is a regression guard.
"""
import re
from datetime import date

import pytest
from fastapi.routing import APIRoute

from app.main import app
from tests.security.world import API

PUBLIC = {("POST", f"{API}/auth/register"), ("POST", f"{API}/auth/login"), ("POST", f"{API}/auth/refresh"),
          ("POST", f"{API}/auth/forgot-password"), ("POST", f"{API}/public/register")}
ZERO = "00000000-0000-0000-0000-000000000001"
QUERY = {"att_date": "2026-10-15", "duty_date": "2026-10-15", "date": "2026-10-15", "on_date": "2026-10-15",
         "month": "10", "year": "2026", "voucher_type": "journal", "department": "security", "for_date": "2026-10-15"}


def _routes(methods=("GET", "POST", "PUT", "PATCH", "DELETE")):
    seen = set()
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith(f"{API}/"):
            for m in r.methods:
                if m in methods:
                    seen.add((m, r.path))
    return sorted(seen)


def _fill(path, society_id=None):
    def rep(m):
        name = m.group(1)
        if name == "society_id" and society_id is not None:
            return str(society_id)
        return {"year": "2026", "month": "6", "fy": "2026-27"}.get(name, ZERO)
    return re.sub(r"\{(\w+)(?::[^}]*)?\}", rep, path)


# ── 1. unauthenticated access ────────────────────────────────────────────────

def test_every_protected_route_rejects_a_request_with_no_token(client):
    leaks = []
    for method, path in _routes():
        if (method, path) in PUBLIC:
            continue
        r = client.request(method, _fill(path), json={} if method != "GET" else None)
        if r.status_code not in (401, 403):
            leaks.append((method, path, r.status_code))
    assert not leaks, f"routes that answered an anonymous call: {leaks}"


# ── 2. cross-society reads, every list/detail/report route that takes a society id ─

def test_no_get_route_with_a_society_id_serves_another_societys_admin(client, world):
    served = []
    for method, path in _routes(("GET",)):
        if "{society_id}" not in path or "platform-admin" in path:
            continue
        r = client.get(_fill(path, world.B.id), headers=world.admin_a["headers"], params=QUERY)
        if r.status_code == 200:
            served.append(path)
    assert not served, f"routes that returned society B's data to society A's admin: {served}"


def test_the_same_routes_do_serve_the_societys_own_admin(client, world):
    """Guards the sweep above against passing for the wrong reason: society B's own admin gets answers."""
    ok = 0
    for method, path in _routes(("GET",)):
        if "{society_id}" not in path or "platform-admin" in path:
            continue
        if client.get(_fill(path, world.B.id), headers=world.admin_b["headers"], params=QUERY).status_code == 200:
            ok += 1
    assert ok >= 40, f"only {ok} society-scoped routes answered the society's own admin; the sweep is not testing much"


# ── 3. workload summaries (were unscoped) ────────────────────────────────────

def test_workload_summaries_are_scoped_to_the_callers_society(client, world):
    a = world.admin_a["headers"]
    assert client.get(f"{API}/workload/society/{world.B.id}/summary", headers=a).status_code == 403
    assert client.get(f"{API}/workload/staff/{world.staff_b.id}/summary", headers=a).status_code == 404
    assert client.get(f"{API}/workload/society/{world.A.id}/summary", headers=a).status_code == 200
    assert client.get(f"{API}/workload/staff/{world.staff_a.id}/summary", headers=a).status_code == 200
    p = world.platform["headers"]
    assert client.get(f"{API}/workload/society/{world.B.id}/summary", headers=p).status_code == 200
    assert client.get(f"{API}/workload/staff/{world.staff_b.id}/summary", headers=p).status_code == 200


# ── 4. staff record by user id (was unscoped for privileged callers) ─────────

def test_staff_by_user_does_not_cross_societies(client, world):
    a = world.admin_a["headers"]
    assert client.get(f"{API}/staff/by-user/{world.staff_b_login['user'].id}", headers=a).status_code == 404
    assert client.get(f"{API}/staff/by-user/{world.security_a['user'].id}", headers=a).status_code == 200
    # a member of staff still reads their own record
    assert client.get(f"{API}/staff/by-user/{world.security_a['user'].id}", headers=world.security_a["headers"]).status_code == 200
    assert client.get(f"{API}/staff/by-user/{world.staff_b_login['user'].id}", headers=world.security_a["headers"]).status_code == 403
    assert client.get(f"{API}/staff/by-user/{world.staff_b_login['user'].id}", headers=world.platform["headers"]).status_code == 200


# ── 5. penalty rules took the society from the request body ──────────────────

def test_penalty_rule_cannot_be_created_in_another_society(client, db, world):
    from app.modules.billing.models.billing import PenaltyRule
    body = lambda sid: {"society_id": str(sid), "name": "Late fee", "rate": 2}
    before = db.query(PenaltyRule).filter_by(society_id=world.B.id).count()
    r = client.post(f"{API}/billing/penalty-rules", json=body(world.B.id), headers=world.manager_a["headers"])
    assert r.status_code == 403, r.text
    assert db.query(PenaltyRule).filter_by(society_id=world.B.id).count() == before
    own = client.post(f"{API}/billing/penalty-rules", json=body(world.A.id), headers=world.manager_a["headers"])
    assert own.status_code == 201 and own.json()["society_id"] == str(world.A.id)
    plat = client.post(f"{API}/billing/penalty-rules", json=body(world.B.id), headers=world.platform["headers"])
    assert plat.status_code == 201 and plat.json()["society_id"] == str(world.B.id)
    assert client.post(f"{API}/billing/penalty-rules", json=body(world.A.id), headers=world.resident_a["headers"]).status_code == 403


# ── 6. receipt numbers repeat across societies ───────────────────────────────

def test_receipt_lookup_by_number_stays_inside_the_callers_society(client, db, world):
    """Every society's first receipt is OPS-2026-00001; the lookup by number alone returned whichever came first."""
    from app.modules.billing.models.billing import OnlinePaymentSubmission, PaymentMode
    from app.modules.billing.services.billing_service import BillingService
    rows = {}
    for key, soc, flat in (("a", world.A, world.flat_a), ("b", world.B, world.flat_b)):   # A's row is stored first
        row = OnlinePaymentSubmission(society_id=soc.id, flat_id=flat.id, receipt_number="OPS-2026-00001",
                                      amount=1500, payment_date=date.today(), payment_mode=PaymentMode.CASH)
        db.add(row); db.commit(); db.refresh(row)
        rows[key] = row
    svc = BillingService(db)
    assert svc.get_payment_by_receipt_number("OPS-2026-00001", world.B.id).id == rows["b"].id
    assert svc.get_payment_by_receipt_number("OPS-2026-00001", world.A.id).id == rows["a"].id
    r = client.get(f"{API}/billing/receipts/OPS-2026-00001/pdf", headers=world.manager_b["headers"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf", r.text[:200]
    # and a society never opens another's receipt by its number
    only_b = OnlinePaymentSubmission(society_id=world.B.id, flat_id=world.flat_b.id, receipt_number="OPS-2026-00002",
                                     amount=10, payment_date=date.today(), payment_mode=PaymentMode.CASH)
    db.add(only_b); db.commit()
    assert client.get(f"{API}/billing/receipts/OPS-2026-00002/pdf", headers=world.manager_a["headers"]).status_code == 404


# ── 7. a resident could reverse a vendor payment ─────────────────────────────

def test_vendor_payment_reversal_needs_a_manager(client, world):
    url = f"{API}/vendors/payments/{ZERO}/reverse"
    body = {"reason": "Entered against the wrong invoice"}
    for who in ("resident_a", "security_a", "supervisor_a"):
        assert client.post(url, json=body, headers=getattr(world, who)["headers"]).status_code == 403, who
    # a manager passes the role check (and then finds no such payment)
    assert client.post(url, json=body, headers=world.manager_a["headers"]).status_code == 404


# ── 8. residents' personal data was readable by every member ─────────────────

def _register_people(client, world):
    """A resident (with identity documents) and a tenant (with rent) in society A, made by the office."""
    from datetime import timedelta
    h = world.admin_a["headers"]            # creating records is for admin and committee; reading is wider
    res = client.post(f"{API}/residents/", json={
        "flat_id": str(world.flat_a.id), "full_name": "Neighbour One", "phone": "9822000001",
        "email": "neighbour.one@example.com",
        "id_proof_type": "Aadhaar", "id_proof_number": "1234 5678 9012", "date_of_birth": "1980-04-02",
        "emergency_contact_name": "Relative", "emergency_contact_phone": "9822000009",
    }, headers=h)
    assert res.status_code == 201, res.text
    ten = client.post(f"{API}/tenants/", json={
        "flat_id": str(world.flat_a.id), "full_name": "Tenant One", "monthly_rent": "21000.00",
        "phone": "9822000002", "email": "tenant.one@example.com",
        "agreement_start_date": str(date.today()), "agreement_end_date": str(date.today() + timedelta(days=300)),
        "id_proof_type": "PAN", "id_proof_number": "ABCDE1234F",
    }, headers=h)
    assert ten.status_code == 201, ten.text
    return res.json(), ten.json()


RESIDENT_PRIVATE = ("phone", "email", "date_of_birth", "id_proof_type", "id_proof_number", "emergency_contact_name",
                    "emergency_contact_phone")
TENANT_PRIVATE = ("phone", "email", "monthly_rent", "id_proof_type", "id_proof_number")


def test_members_see_neighbours_but_not_their_contact_details_identity_documents_or_rent(client, world):
    res, ten = _register_people(client, world)
    for who in ("resident_a", "security_a"):
        h = getattr(world, who)["headers"]
        listed = client.get(f"{API}/residents/", headers=h)
        assert listed.status_code == 200
        row = next(r for r in listed.json() if r["id"] == res["id"])
        assert row["full_name"] == "Neighbour One"
        assert all(row[f] is None for f in RESIDENT_PRIVATE), (who, row)
        one = client.get(f"{API}/residents/{res['id']}", headers=h).json()
        assert all(one[f] is None for f in RESIDENT_PRIVATE)
        t = client.get(f"{API}/tenants/{ten['id']}", headers=h).json()
        assert t["full_name"] == "Tenant One" and all(t[f] is None for f in TENANT_PRIVATE), (who, t)
        assert all(x["monthly_rent"] is None for x in client.get(f"{API}/tenants/", headers=h).json())


def test_the_office_still_sees_everything(client, world):
    res, ten = _register_people(client, world)
    for who in ("manager_a", "admin_a", "committee_a"):
        h = getattr(world, who)["headers"]
        r = client.get(f"{API}/residents/{res['id']}", headers=h).json()
        assert r["id_proof_number"] == "1234 5678 9012" and r["date_of_birth"] == "1980-04-02", who
        assert r["phone"] == "9822000001" and r["email"] == "neighbour.one@example.com", who
        t = client.get(f"{API}/tenants/{ten['id']}", headers=h).json()
        assert t["monthly_rent"] == "21000.00" and t["id_proof_number"] == "ABCDE1234F", who
        assert t["phone"] == "9822000002" and t["email"] == "tenant.one@example.com", who


def test_a_resident_sees_their_own_record_in_full(client, db, world):
    res, _ = _register_people(client, world)
    client.patch(f"{API}/residents/{res['id']}", json={"user_id": str(world.resident_a["user"].id)},
                 headers=world.admin_a["headers"])
    own = client.get(f"{API}/residents/{res['id']}", headers=world.resident_a["headers"]).json()
    assert own["id_proof_number"] == "1234 5678 9012"
    assert own["phone"] == "9822000001" and own["email"] == "neighbour.one@example.com"


def test_a_member_cannot_look_a_person_up_by_phone_or_email(client, world):
    """The phone number is hidden from the results; searching by it must not confirm whose it is either."""
    res, ten = _register_people(client, world)
    for who in ("resident_a", "security_a"):
        h = getattr(world, who)["headers"]
        for term in ("9822000001", "neighbour.one@example.com"):
            assert client.get(f"{API}/residents/", params={"search": term}, headers=h).json() == [], (who, term)
        for term in ("9822000002", "tenant.one@example.com"):
            assert client.get(f"{API}/tenants/", params={"search": term}, headers=h).json() == [], (who, term)
        # a name still finds the neighbour: that is the directory
        assert [r["id"] for r in client.get(f"{API}/residents/", params={"search": "Neighbour"}, headers=h).json()] == [res["id"]]
        assert [t["id"] for t in client.get(f"{API}/tenants/", params={"search": "Tenant One"}, headers=h).json()] == [ten["id"]]
    for who in ("manager_a", "admin_a"):
        h = getattr(world, who)["headers"]
        assert [r["id"] for r in client.get(f"{API}/residents/", params={"search": "9822000001"}, headers=h).json()] == [res["id"]], who
        assert [t["id"] for t in client.get(f"{API}/tenants/", params={"search": "tenant.one@"}, headers=h).json()] == [ten["id"]], who


def test_rent_agreements_and_occupancy_history_stay_with_the_office(client, world):
    res, ten = _register_people(client, world)
    r, s = world.resident_a["headers"], world.security_a["headers"]
    for h in (r, s):
        assert client.get(f"{API}/tenants/{ten['id']}/agreements", headers=h).status_code == 403
        assert client.get(f"{API}/occupancy/flat/{world.flat_a.id}/history", headers=h).status_code == 403
    m = world.manager_a["headers"]
    assert client.get(f"{API}/tenants/{ten['id']}/agreements", headers=m).status_code == 200
    assert client.get(f"{API}/occupancy/flat/{world.flat_a.id}/history", headers=m).status_code == 200
    for url in (f"{API}/residents/mine", f"{API}/auth/me", f"{API}/billing/bills/me"):
        assert client.get(url, headers=r).status_code == 200, url


def test_register_reads_stay_inside_the_callers_society(client, world):
    res, ten = _register_people(client, world)
    b = world.manager_b["headers"]
    assert client.get(f"{API}/residents/{res['id']}", headers=b).status_code == 404
    assert client.get(f"{API}/tenants/{ten['id']}", headers=b).status_code == 404
    assert all(r["id"] != res["id"] for r in client.get(f"{API}/residents/", headers=b).json())
    assert client.get(f"{API}/occupancy/flat/{world.flat_a.id}/history", headers=b).status_code in (403, 404)


# ── 9. a login with no society (what public registration creates) ────────────

def _register_and_login(client, email="stranger@example.com"):
    r = client.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "full_name": "Stranger",
                                                    "phone": "9000000099"})
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_a_self_registered_login_without_a_society_sees_no_society_data(client, world):
    h = _register_and_login(client)
    for url in (f"{API}/societies/{world.A.id}", f"{API}/flats/by-society/{world.A.id}",
                f"{API}/wings/by-society/{world.A.id}", f"{API}/vehicles/society/{world.A.id}",
                f"{API}/notices/society/{world.A.id}/published", f"{API}/governance/documents/society/{world.A.id}",
                f"{API}/gate/help/society/{world.A.id}", f"{API}/certificates/society/{world.A.id}",
                f"{API}/parking/zones/{world.A.id}", f"{API}/amenities/society/{world.A.id}",
                f"{API}/visitors/gates/{world.A.id}", f"{API}/societies/", f"{API}/flats/", f"{API}/wings/"):
        r = client.get(url, headers=h)
        assert r.status_code == 403, (url, r.status_code, r.text[:120])
        assert "not linked to a society" in r.json()["detail"]


def test_a_login_without_a_society_can_still_manage_its_own_sign_in(client, world):
    h = _register_and_login(client, "keeps-signin@example.com")
    assert client.get(f"{API}/auth/me", headers=h).status_code == 200
    assert client.get(f"{API}/auth/sessions", headers=h).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=h).status_code == 204


def test_once_linked_to_a_society_the_login_sees_only_that_society(client, db, world):
    from app.models.user import User
    h = _register_and_login(client, "linked@example.com")
    u = db.query(User).filter(User.email == "linked@example.com").one()
    u.society_id = world.A.id
    db.commit()
    assert client.get(f"{API}/societies/{world.A.id}", headers=h).status_code == 200
    assert client.get(f"{API}/societies/{world.B.id}", headers=h).status_code == 403


def test_platform_admin_keeps_its_cross_society_reach(client, world):
    p = world.platform["headers"]
    assert client.get(f"{API}/societies/{world.A.id}", headers=p).status_code == 200
    assert client.get(f"{API}/societies/{world.B.id}", headers=p).status_code == 200
    assert client.get(f"{API}/flats/by-society/{world.B.id}", headers=p).status_code == 200


# ── 10. roles: the office can do what residents and staff cannot ─────────────

@pytest.mark.parametrize("who", ["resident_a", "security_a", "supervisor_a"])
def test_non_office_roles_cannot_use_administrative_endpoints(client, world, who):
    h = getattr(world, who)["headers"]
    assert client.get(f"{API}/users/", headers=h).status_code == 403
    assert client.post(f"{API}/users/", json={"email": "x@y.zz", "full_name": "X Y", "role_name": "Resident"}, headers=h).status_code == 403
    assert client.post(f"{API}/billing/penalty-rules", json={"society_id": str(world.A.id), "name": "n", "rate": 1}, headers=h).status_code == 403
    assert client.get(f"{API}/accounts/summary/{world.A.id}", headers=h).status_code == 403
    assert client.get(f"{API}/billing/cycles/{world.A.id}", headers=h).status_code == 403


def test_committee_member_reads_but_cannot_administer(client, world):
    h = world.committee_a["headers"]
    assert client.get(f"{API}/billing/penalty-rules/{world.A.id}", headers=h).status_code == 200
    assert client.get(f"{API}/users/", headers=h).status_code == 403                       # admin only
    assert client.post(f"{API}/users/", json={"email": "x@y.zz", "full_name": "X Y", "role_name": "Resident"}, headers=h).status_code == 403


# ── 11. the permission matrix leaves a trail ─────────────────────────────────

def test_changing_the_permission_matrix_is_audited(client, db, world):
    from app.models.audit_log import AuditLog
    from app.models.role import Role
    role = db.query(Role).filter(Role.name == "Resident").one()
    codes = sorted(rp.permission.code for rp in role.role_permissions)
    r = client.put(f"{API}/roles/{role.id}/permissions", json={"permission_codes": codes}, headers=world.admin_a["headers"])
    assert r.status_code == 200, r.text
    row = db.query(AuditLog).filter(AuditLog.module == "rbac", AuditLog.entity_id == str(role.id)).one()
    assert row.user_email == "admin@a.sec"
    assert row.new_values["permission_codes"] == codes
    forms = sorted(rf.form.code for rf in role.role_forms)
    r = client.put(f"{API}/roles/{role.id}/forms", json={"form_codes": forms}, headers=world.admin_a["headers"])
    assert r.status_code == 200, r.text
    assert db.query(AuditLog).filter(AuditLog.module == "rbac", AuditLog.entity_id == str(role.id)).count() == 2
    # a resident cannot touch the matrix at all
    assert client.put(f"{API}/roles/{role.id}/permissions", json={"permission_codes": codes},
                      headers=world.resident_a["headers"]).status_code == 403
