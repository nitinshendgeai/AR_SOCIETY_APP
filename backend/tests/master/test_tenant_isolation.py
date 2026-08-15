"""
Master domain — tenant isolation + AgreementTracker.society_id regression tests.

These exercise two fixes:
  1. Society/Wing/Floor/Flat/Vehicle/Occupancy endpoints must scope every
     read/update/delete to the caller's own society, not just check role.
  2. OccupancyService.tenant_move_in() must derive AgreementTracker.society_id
     from the flat's wing, not hardcode it to None (which permanently broke
     get_expiring_agreements — see Phase M1 audit).

Unlike most of the existing test suite, these use society-scoped callers
(user.society_id explicitly set) rather than the default unscoped
"platform admin" test user, since the bugs here only manifest for a
caller who actually belongs to a society.
"""
import pytest
from datetime import date, timedelta
from uuid import UUID as _UUID
from tests.conftest import make_user, make_society, make_wing, make_flat


def _to_uuid(v) -> _UUID:
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def two_societies(db):
    """Two independent societies, each with an admin scoped to it, and a
    wing/flat under each — the standard cross-tenant test fixture."""
    society_a = make_society(db, "Isolation Society A")
    society_b = make_society(db, "Isolation Society B")

    admin_a = make_user(db, "admA@iso.com", role="Society Admin")
    admin_b = make_user(db, "admB@iso.com", role="Society Admin")
    _set_society(db, admin_a["user"], society_a.id)
    _set_society(db, admin_b["user"], society_b.id)

    wing_a = make_wing(db, society_a.id, "Wing A1")
    wing_b = make_wing(db, society_b.id, "Wing B1")
    flat_a = make_flat(db, wing_a.id, "A-101")
    flat_b = make_flat(db, wing_b.id, "B-101")

    return {
        "society_a": society_a, "society_b": society_b,
        "admin_a": admin_a, "admin_b": admin_b,
        "wing_a": wing_a, "wing_b": wing_b,
        "flat_a": flat_a, "flat_b": flat_b,
    }


# ── Society ───────────────────────────────────────────────────────────────────

def test_society_admin_cannot_patch_other_society(client, db, two_societies):
    t = two_societies
    r = client.patch(f"/api/v1/societies/{t['society_b'].id}",
                      json={"city": "Hijacked"}, headers=t["admin_a"]["headers"])
    assert r.status_code == 403


def test_society_admin_cannot_delete_other_society(client, db, two_societies):
    t = two_societies
    r = client.delete(f"/api/v1/societies/{t['society_b'].id}", headers=t["admin_a"]["headers"])
    assert r.status_code == 403


def test_society_admin_can_patch_own_society(client, db, two_societies):
    t = two_societies
    r = client.patch(f"/api/v1/societies/{t['society_a'].id}",
                      json={"city": "Own City"}, headers=t["admin_a"]["headers"])
    assert r.status_code == 200


# ── Wing ──────────────────────────────────────────────────────────────────────

def test_wing_cross_society_read_blocked(client, db, two_societies):
    t = two_societies
    r = client.get(f"/api/v1/wings/{t['wing_b'].id}", headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_wing_list_scoped_to_own_society(client, db, two_societies):
    t = two_societies
    r = client.get("/api/v1/wings/", headers=t["admin_a"]["headers"])
    assert r.status_code == 200
    ids = [w["id"] for w in r.json()]
    assert str(t["wing_a"].id) in ids
    assert str(t["wing_b"].id) not in ids


def test_wing_cross_society_update_blocked(client, db, two_societies):
    t = two_societies
    r = client.patch(f"/api/v1/wings/{t['wing_b'].id}", json={"name": "Hijacked"},
                      headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_wing_cross_society_delete_blocked(client, db, two_societies):
    t = two_societies
    r = client.delete(f"/api/v1/wings/{t['wing_b'].id}", headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_wing_create_for_other_society_rejected(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/wings/", json={
        "name": "Sneaky Wing", "society_id": str(t["society_b"].id),
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 403


def test_wing_create_own_society_still_works(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/wings/", json={
        "name": "Legit Wing", "society_id": str(t["society_a"].id),
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 201


# ── Flat ──────────────────────────────────────────────────────────────────────

def test_flat_cross_society_read_blocked(client, db, two_societies):
    t = two_societies
    r = client.get(f"/api/v1/flats/{t['flat_b'].id}", headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_flat_list_scoped_to_own_society(client, db, two_societies):
    t = two_societies
    r = client.get("/api/v1/flats/", headers=t["admin_a"]["headers"])
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()]
    assert str(t["flat_a"].id) in ids
    assert str(t["flat_b"].id) not in ids


def test_flat_create_under_other_societys_wing_rejected(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/flats/", json={
        "flat_number": "999", "wing_id": str(t["wing_b"].id),
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_flat_cross_society_delete_blocked(client, db, two_societies):
    t = two_societies
    r = client.delete(f"/api/v1/flats/{t['flat_b'].id}", headers=t["admin_a"]["headers"])
    assert r.status_code == 404


# ── Vehicle ───────────────────────────────────────────────────────────────────

def test_vehicle_cross_society_read_update_delete_blocked(client, db, two_societies):
    t = two_societies
    from app.models.vehicle import Vehicle
    v = Vehicle(society_id=t["society_b"].id, vehicle_number="MH12ZZ0001", vehicle_type="car")
    db.add(v); db.commit(); db.refresh(v)

    assert client.get(f"/api/v1/vehicles/{v.id}", headers=t["admin_a"]["headers"]).status_code == 404
    assert client.patch(f"/api/v1/vehicles/{v.id}", json={"color": "red"},
                         headers=t["admin_a"]["headers"]).status_code == 404
    assert client.delete(f"/api/v1/vehicles/{v.id}", headers=t["admin_a"]["headers"]).status_code == 404


def test_vehicle_list_by_society_cross_tenant_blocked(client, db, two_societies):
    t = two_societies
    r = client.get(f"/api/v1/vehicles/society/{t['society_b'].id}", headers=t["admin_a"]["headers"])
    assert r.status_code == 403


def test_vehicle_create_for_other_society_rejected(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(t["society_b"].id), "vehicle_number": "MH12ZZ0002", "vehicle_type": "car",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 403


# ── Occupancy / AgreementTracker.society_id fix ─────────────────────────────────

def test_resident_move_in_cross_society_blocked(client, db, two_societies):
    """Admin A cannot move a resident into a flat that belongs to Society B."""
    t = two_societies
    from app.models.resident import Resident
    res = Resident(full_name="Cross Tenant Resident", flat_id=t["flat_b"].id)
    db.add(res); db.commit(); db.refresh(res)

    r = client.post("/api/v1/occupancy/resident/move-in", json={
        "flat_id": str(t["flat_b"].id), "resident_id": str(res.id),
        "move_in_date": str(date.today()),
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_tenant_move_in_sets_correct_agreement_society_id(client, db, two_societies):
    """Regression test for the AgreementTracker.society_id=None bug: after a
    tenant move-in with an agreement, the created AgreementTracker row must
    carry the flat's real society_id, not None."""
    t = two_societies
    from app.models.tenant import Tenant
    from app.models.agreement_tracker import AgreementTracker

    start = date.today()
    end   = start + timedelta(days=10)
    tenant = Tenant(
        full_name="Regression Tenant", flat_id=t["flat_a"].id,
        agreement_start_date=start, agreement_end_date=end,
        monthly_rent=15000,
    )
    db.add(tenant); db.commit(); db.refresh(tenant)

    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(t["flat_a"].id), "tenant_id": str(tenant.id),
        "move_in_date": str(start), "create_agreement": True,
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 200, r.text

    agr = db.query(AgreementTracker).filter(AgreementTracker.tenant_id == tenant.id).first()
    assert agr is not None, "AgreementTracker row should have been created"
    assert agr.society_id is not None, "AgreementTracker.society_id must not be None"
    assert agr.society_id == t["society_a"].id


def test_expiring_agreements_finds_the_agreement_it_just_created(client, db, two_societies):
    """Before the fix, every AgreementTracker had society_id=None, so this
    query (which filters by society_id) could never return anything —
    the 'expiring agreements' feature was permanently broken. This proves
    it now actually works end to end."""
    t = two_societies
    from app.models.tenant import Tenant

    start = date.today()
    end   = start + timedelta(days=10)
    tenant = Tenant(
        full_name="Expiry Tenant", flat_id=t["flat_a"].id,
        agreement_start_date=start, agreement_end_date=end,
    )
    db.add(tenant); db.commit(); db.refresh(tenant)

    move_in = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(t["flat_a"].id), "tenant_id": str(tenant.id),
        "move_in_date": str(start), "create_agreement": True,
    }, headers=t["admin_a"]["headers"])
    assert move_in.status_code == 200

    r = client.get(
        f"/api/v1/occupancy/agreements/expiring/{t['society_a'].id}?days=30",
        headers=t["admin_a"]["headers"],
    )
    assert r.status_code == 200
    tenant_ids = [a["tenant_id"] for a in r.json()]
    assert str(tenant.id) in tenant_ids


def test_expiring_agreements_cross_society_blocked(client, db, two_societies):
    t = two_societies
    r = client.get(
        f"/api/v1/occupancy/agreements/expiring/{t['society_b'].id}",
        headers=t["admin_a"]["headers"],
    )
    assert r.status_code == 403


def test_flat_history_cross_society_blocked(client, db, two_societies):
    t = two_societies
    r = client.get(f"/api/v1/occupancy/flat/{t['flat_b'].id}/history",
                    headers=t["admin_a"]["headers"])
    assert r.status_code == 404


# ── Resident (Phase M1.2) ─────────────────────────────────────────────────────
# Extends this file's existing cross-tenant matrix to the new /residents/*
# endpoints, using the same two_societies fixture as everything above.

def test_resident_get_own_society_allowed(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Own Society Resident",
    }, headers=t["admin_a"]["headers"]).json()
    r = client.get(f"/api/v1/residents/{created['id']}", headers=t["admin_a"]["headers"])
    assert r.status_code == 200


def test_resident_get_cross_society_denied(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Resident",
    }, headers=t["admin_b"]["headers"]).json()
    r = client.get(f"/api/v1/residents/{created['id']}", headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_resident_patch_own_society_allowed(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Editable Own Resident",
    }, headers=t["admin_a"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"phone": "9123456780"},
                      headers=t["admin_a"]["headers"])
    assert r.status_code == 200


def test_resident_patch_cross_society_denied(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Editable",
    }, headers=t["admin_b"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"phone": "9123456781"},
                      headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_resident_post_into_own_flat_allowed(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Legit New Resident",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 201


def test_resident_post_into_other_societys_flat_denied(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Cross Tenant Injection Attempt",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_resident_list_own_society_only(client, db, two_societies):
    t = two_societies
    client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "List Test A",
    }, headers=t["admin_a"]["headers"])
    client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "List Test B",
    }, headers=t["admin_b"]["headers"])
    r = client.get("/api/v1/residents/", headers=t["admin_a"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "List Test A" in names
    assert "List Test B" not in names


def test_resident_occupancy_move_in_wrong_flat_for_resident_denied(client, db, two_societies):
    """A resident whose flat_id doesn't match the flat_id supplied to
    move-in must be rejected, even within the same society — this is the
    Resident.flat_id == flat_id guard added to OccupancyService in the P0
    fix, re-verified here now that Resident rows are actually creatable."""
    t = two_societies
    resident_on_a = client.post("/api/v1/residents/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Bound To Flat A",
    }, headers=t["admin_a"]["headers"]).json()

    # Reuse the fixture's existing wing_a (make_wing() hardcodes code="A", so
    # a second wing in the same society would collide with the
    # (society_id, code) unique constraint) — a second flat under it is
    # enough for this test.
    other_flat_same_society = make_flat(db, t["wing_a"].id, "A-extra-101")

    r = client.post("/api/v1/occupancy/resident/move-in", json={
        "flat_id": str(other_flat_same_society.id),
        "resident_id": resident_on_a["id"],
        "move_in_date": "2026-08-15",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404, "a resident cannot be moved into a flat that isn't their own"


# ── Tenant (Phase M1.3) ───────────────────────────────────────────────────────
# Same matrix as the Resident section above, applied to /tenants/* and the
# agreement-renewal endpoint, using the same two_societies fixture.

def test_tenant_get_own_society_allowed(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Own Society Tenant",
    }, headers=t["admin_a"]["headers"]).json()
    r = client.get(f"/api/v1/tenants/{created['id']}", headers=t["admin_a"]["headers"])
    assert r.status_code == 200


def test_tenant_get_cross_society_denied(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Tenant",
    }, headers=t["admin_b"]["headers"]).json()
    r = client.get(f"/api/v1/tenants/{created['id']}", headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_tenant_patch_own_society_allowed(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Editable Own Tenant",
    }, headers=t["admin_a"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"phone": "9123456790"},
                      headers=t["admin_a"]["headers"])
    assert r.status_code == 200


def test_tenant_patch_cross_society_denied(client, db, two_societies):
    t = two_societies
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Editable Tenant",
    }, headers=t["admin_b"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"phone": "9123456791"},
                      headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_tenant_post_into_own_flat_allowed(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "Legit New Tenant",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 201


def test_tenant_post_into_other_societys_flat_denied(client, db, two_societies):
    t = two_societies
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Cross Tenant Injection Attempt",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_tenant_list_own_society_only(client, db, two_societies):
    t = two_societies
    client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_a"].id), "full_name": "List Test Tenant A",
    }, headers=t["admin_a"]["headers"])
    client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "List Test Tenant B",
    }, headers=t["admin_b"]["headers"])
    r = client.get("/api/v1/tenants/", headers=t["admin_a"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "List Test Tenant A" in names
    assert "List Test Tenant B" not in names


def test_tenant_move_in_cross_society_denied(client, db, two_societies):
    t = two_societies
    tenant_on_b = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Tenant For Move-in",
    }, headers=t["admin_b"]["headers"]).json()
    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(t["flat_b"].id), "tenant_id": tenant_on_b["id"],
        "move_in_date": "2026-08-15",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_tenant_move_out_cross_society_denied(client, db, two_societies):
    t = two_societies
    tenant_on_b = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Tenant For Move-out",
        "move_in_date": "2026-08-15",
    }, headers=t["admin_b"]["headers"]).json()
    r = client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(t["flat_b"].id), "tenant_id": tenant_on_b["id"],
        "move_out_date": "2026-08-16",
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


def test_agreement_renewal_cross_society_denied(client, db, two_societies):
    t = two_societies
    from datetime import date, timedelta
    start = date.today()
    end = start + timedelta(days=180)
    tenant_on_b = client.post("/api/v1/tenants/", json={
        "flat_id": str(t["flat_b"].id), "full_name": "Society B Tenant For Renewal",
        "agreement_start_date": str(start), "agreement_end_date": str(end),
        "move_in_date": str(start),
    }, headers=t["admin_b"]["headers"]).json()
    r = client.post(f"/api/v1/tenants/{tenant_on_b['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end + timedelta(days=90)),
    }, headers=t["admin_a"]["headers"])
    assert r.status_code == 404


# ── Vehicle DB-level constraint enforcement (Phase M1.3) ─────────────────────
# Mirrors TestResidentDatabaseConstraints (Phase M1.2) — proves the DATABASE
# rejects invalid rows, not just the application layer, including via raw
# SQL that bypasses the ORM/Pydantic validation entirely.

class TestVehicleDatabaseConstraints:

    def test_db_rejects_normalized_duplicate_vehicle_number(self, db, two_societies):
        from app.models.vehicle import Vehicle
        from sqlalchemy.exc import IntegrityError
        t = two_societies
        v1 = Vehicle(society_id=t["society_a"].id, flat_id=t["flat_a"].id, vehicle_number="MH07XY0001")
        db.add(v1); db.commit()

        v2 = Vehicle(society_id=t["society_a"].id, flat_id=t["flat_a"].id, vehicle_number="mh-07-xy-0001")
        db.add(v2)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_db_allows_same_number_in_different_society(self, db, two_societies):
        from app.models.vehicle import Vehicle
        t = two_societies
        v1 = Vehicle(society_id=t["society_a"].id, flat_id=t["flat_a"].id, vehicle_number="MH07XY0002")
        v2 = Vehicle(society_id=t["society_b"].id, flat_id=t["flat_b"].id, vehicle_number="MH07XY0002")
        db.add_all([v1, v2])
        db.commit()  # must not raise

    def test_db_rejects_resident_and_tenant_both_set_via_raw_sql(self, db, two_societies):
        """Bypasses the Pydantic XOR validator entirely (raw SQL) — proves
        the CHECK constraint, not application code, is what actually stops
        this."""
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        from app.models.resident import Resident
        from app.models.tenant import Tenant
        t = two_societies
        resident = Resident(flat_id=t["flat_a"].id, full_name="Vehicle XOR Resident")
        tenant = Tenant(flat_id=t["flat_a"].id, full_name="Vehicle XOR Tenant")
        db.add_all([resident, tenant]); db.commit()
        db.refresh(resident); db.refresh(tenant)

        with pytest.raises(IntegrityError):
            db.execute(text("""
                INSERT INTO vehicles (id, created_at, updated_at, is_active, society_id, flat_id,
                                       resident_id, tenant_id, vehicle_number, vehicle_type)
                VALUES (lower(hex(randomblob(16))), datetime('now'), datetime('now'), 1,
                        :sid, :fid, :rid, :tid, 'MH07XY0003', 'car')
            """), {"sid": t["society_a"].id.hex, "fid": t["flat_a"].id.hex,
                    "rid": resident.id.hex, "tid": tenant.id.hex})
            db.commit()

    def test_db_allows_resident_only_via_raw_sql(self, db, two_societies):
        from sqlalchemy import text
        from app.models.resident import Resident
        t = two_societies
        resident = Resident(flat_id=t["flat_a"].id, full_name="Vehicle XOR OK Resident")
        db.add(resident); db.commit(); db.refresh(resident)
        db.execute(text("""
            INSERT INTO vehicles (id, created_at, updated_at, is_active, society_id, flat_id,
                                   resident_id, vehicle_number, vehicle_type)
            VALUES (lower(hex(randomblob(16))), datetime('now'), datetime('now'), 1,
                    :sid, :fid, :rid, 'MH07XY0004', 'car')
        """), {"sid": t["society_a"].id.hex, "fid": t["flat_a"].id.hex, "rid": resident.id.hex})
        db.commit()  # must not raise


class TestAgreementRenewalFK:

    def test_db_rejects_orphaned_renewal_of_id(self, db, two_societies):
        import uuid
        from datetime import date
        from sqlalchemy.exc import IntegrityError
        from app.models.tenant import Tenant
        from app.models.agreement_tracker import AgreementTracker, AgreementStatus
        t = two_societies
        tenant = Tenant(flat_id=t["flat_a"].id, full_name="FK Test Tenant")
        db.add(tenant); db.commit(); db.refresh(tenant)

        agr = AgreementTracker(
            society_id=t["society_a"].id, flat_id=t["flat_a"].id, tenant_id=tenant.id,
            start_date=date(2026, 1, 1), end_date=date(2026, 6, 30), status=AgreementStatus.ACTIVE,
            renewal_of_id=uuid.uuid4(),
        )
        db.add(agr)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_db_allows_renewal_of_id_pointing_at_real_agreement(self, db, two_societies):
        from datetime import date
        from app.models.tenant import Tenant
        from app.models.agreement_tracker import AgreementTracker, AgreementStatus
        t = two_societies
        tenant = Tenant(flat_id=t["flat_a"].id, full_name="FK Test Tenant 2")
        db.add(tenant); db.commit(); db.refresh(tenant)

        agr1 = AgreementTracker(
            society_id=t["society_a"].id, flat_id=t["flat_a"].id, tenant_id=tenant.id,
            start_date=date(2026, 1, 1), end_date=date(2026, 6, 30), status=AgreementStatus.RENEWED,
        )
        db.add(agr1); db.commit(); db.refresh(agr1)

        agr2 = AgreementTracker(
            society_id=t["society_a"].id, flat_id=t["flat_a"].id, tenant_id=tenant.id,
            start_date=date(2026, 6, 30), end_date=date(2026, 12, 31), status=AgreementStatus.ACTIVE,
            renewal_of_id=agr1.id,
        )
        db.add(agr2)
        db.commit()  # must not raise
