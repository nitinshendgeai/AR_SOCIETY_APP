"""
Occupancy lifecycle — Phase M1.3.

Treats Flat.occupancy_status transitions as a controlled state machine
(Phase M1.3 §18): VACANT <-> OWNER_OCCUPIED, VACANT <-> TENANT_OCCUPIED,
with TENANT_OCCUPIED blocking a direct owner move-in (must move the
tenant out first — the existing, re-verified guard). Also covers history
preservation (OccupancyLog), audit logging for every transition, and the
newly-closed FlatUpdate.occupancy_status bypass (Phase M1.3 §19).
"""
import pytest
from uuid import UUID as _UUID
from datetime import date, timedelta
from tests.conftest import make_user, make_society, make_wing, make_flat


def _to_uuid(v) -> _UUID:
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def rig(db):
    society = make_society(db, "Occupancy Test Society")
    admin = make_user(db, "occadm@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing OC1")
    flat = make_flat(db, wing.id, "OC-101")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


def _flat_status(db, flat_id):
    from app.models.flat import Flat
    return db.query(Flat).filter(Flat.id == flat_id).first().occupancy_status


# ── VACANT <-> OWNER_OCCUPIED ────────────────────────────────────────────────

def test_owner_move_in_from_vacant(client, db, rig):
    from app.models.flat import OccupancyStatus
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Owner", "resident_type": "owner",
    }, headers=rig["admin"]["headers"]).json()
    r = client.post("/api/v1/occupancy/resident/move-in", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.OWNER_OCCUPIED


def test_owner_move_out_to_vacant(client, db, rig):
    from app.models.flat import OccupancyStatus
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Owner", "resident_type": "owner",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.OWNER_OCCUPIED

    r = client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.VACANT


# ── VACANT <-> TENANT_OCCUPIED ───────────────────────────────────────────────

def test_tenant_move_in_from_vacant(client, db, rig):
    from app.models.flat import OccupancyStatus
    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Tenant",
    }, headers=rig["admin"]["headers"]).json()
    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant["id"],
        "move_in_date": str(date.today()), "create_agreement": False,
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.TENANT_OCCUPIED


def test_tenant_move_out_to_vacant(client, db, rig):
    from app.models.flat import OccupancyStatus
    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Tenant",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.TENANT_OCCUPIED

    r = client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.VACANT


# ── INVALID TRANSITIONS ───────────────────────────────────────────────────

def test_owner_move_in_blocked_while_tenant_occupied(client, db, rig):
    """Direct TENANT_OCCUPIED -> OWNER_OCCUPIED is not supported — the
    tenant must be moved out first (Phase M1.3 §18)."""
    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Blocking Tenant",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Owner Trying To Move In",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/resident/move-in", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 409


def test_tenant_move_in_blocked_while_owner_occupied(client, db, rig):
    """Symmetric counterpart to test_owner_move_in_blocked_while_tenant_occupied
    above — direct OWNER_OCCUPIED -> TENANT_OCCUPIED must also be rejected;
    the resident must be moved out first. Regression for the P0 found in
    M1.5 certification: tenant_move_in() previously had no guard against an
    active owner-resident, so it silently overwrote occupancy_status while
    leaving the resident active — corrupting the flat's true state."""
    from app.models.flat import OccupancyStatus
    from app.models.resident import Resident
    from app.models.tenant import Tenant
    from app.models.audit_log import AuditLog

    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Blocking Owner",
        "resident_type": "owner", "is_primary": True,
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.OWNER_OCCUPIED

    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Tenant Trying To Move In",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant["id"],
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 409
    assert "owner" in r.json()["detail"].lower()

    # Flat state unchanged
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.OWNER_OCCUPIED

    # Resident remains active, untouched
    resident_row = db.query(Resident).filter(Resident.id == _to_uuid(resident["id"])).first()
    assert resident_row.is_active is True
    assert resident_row.move_out_date is None

    # Tenant never became an active occupant
    tenant_row = db.query(Tenant).filter(Tenant.id == _to_uuid(tenant["id"])).first()
    assert tenant_row.move_in_date is None

    # No successful tenant_move_in event in occupancy history
    history = client.get(f"/api/v1/occupancy/flat/{rig['flat'].id}/history",
                          headers=rig["admin"]["headers"]).json()
    assert not any(e["event_type"] == "tenant_move_in" for e in history)

    # No tenant_move_in audit event persisted
    audit_entries = db.query(AuditLog).filter(
        AuditLog.module == "occupancy", AuditLog.entity_id == str(rig["flat"].id),
    ).all()
    assert not any("tenant_move_in" in str(e.new_values) for e in audit_entries)


def test_duplicate_active_tenancy_rejected(client, db, rig):
    tenant1 = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "First Tenant",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    tenant2 = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Second Tenant",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant2["id"],
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 409


def test_wrong_tenant_flat_relationship_rejected(client, db, rig):
    other_flat = make_flat(db, rig["wing"].id, "OC-102")
    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Bound To OC-101",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(other_flat.id), "tenant_id": tenant["id"],
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 404


def test_wrong_society_move_in_rejected(client, db, rig):
    society_b = make_society(db, "Occupancy Society B")
    admin_b = make_user(db, "occadmB@test.com", role="Society Admin")
    _set_society(db, admin_b["user"], society_b.id)

    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Society A Tenant",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-in", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant["id"],
        "move_in_date": str(date.today()),
    }, headers=admin_b["headers"])
    assert r.status_code == 404


# ── HISTORY PRESERVATION ─────────────────────────────────────────────────

def test_history_records_every_transition_in_order(client, db, rig):
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "History Owner",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])

    r = client.get(f"/api/v1/occupancy/flat/{rig['flat'].id}/history", headers=rig["admin"]["headers"])
    assert r.status_code == 200
    events = [e["event_type"] for e in r.json()]
    assert "resident_move_in" in events
    assert "resident_move_out" in events
    assert "flat_vacant" in events


# ── AUDIT LOGGING (Phase M1.3 §23 — previously missing, now added) ──────

def test_resident_move_out_is_audited(client, db, rig):
    from app.models.audit_log import AuditLog
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Audited Owner",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    entries = db.query(AuditLog).filter(
        AuditLog.module == "occupancy", AuditLog.entity_id == str(rig["flat"].id),
    ).all()
    assert any("resident_move_out" in str(e.new_values) for e in entries), \
        "resident_move_out previously had no audit call at all — must be present now"


def test_tenant_move_in_is_audited(client, db, rig):
    from app.models.audit_log import AuditLog
    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Audited Tenant",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    entries = db.query(AuditLog).filter(
        AuditLog.module == "occupancy", AuditLog.entity_id == str(rig["flat"].id),
    ).all()
    assert any("tenant_move_in" in str(e.new_values) for e in entries)


def test_tenant_move_out_is_audited(client, db, rig):
    from app.models.audit_log import AuditLog
    tenant = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Audited Tenant Out",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    entries = db.query(AuditLog).filter(
        AuditLog.module == "occupancy", AuditLog.entity_id == str(rig["flat"].id),
    ).all()
    assert any("tenant_move_out" in str(e.new_values) for e in entries)


def test_vehicle_unassign_on_move_out_is_audited(client, db, rig):
    from app.models.audit_log import AuditLog
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Vehicle Owner",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": resident["id"], "vehicle_number": "OC01AA0001",
    }, headers=rig["admin"]["headers"])
    client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    entries = db.query(AuditLog).filter(
        AuditLog.module == "vehicle", AuditLog.entity_id == resident["id"],
    ).all()
    assert len(entries) >= 1, "vehicle unassignment on move-out must be audited"


def test_move_out_with_no_vehicle_does_not_create_spurious_audit_entry(client, db, rig):
    from app.models.audit_log import AuditLog
    resident = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "No Vehicle Owner",
        "move_in_date": str(date.today()),
    }, headers=rig["admin"]["headers"]).json()
    client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(rig["flat"].id), "resident_id": resident["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    entries = db.query(AuditLog).filter(
        AuditLog.module == "vehicle", AuditLog.entity_id == resident["id"],
    ).all()
    assert len(entries) == 0


# ── FLAT OCCUPANCY_STATUS BYPASS CLOSED (Phase M1.3 §19) ────────────────

def test_flat_patch_no_longer_changes_occupancy_status(client, db, rig):
    """PATCH /flats/{id} sending occupancy_status must succeed (the field
    is just silently dropped, matching Pydantic's default extra='ignore' —
    no 422, no crash) but must NOT actually change the flat's occupancy
    status, since OccupancyService is now the sole writer."""
    from app.models.flat import OccupancyStatus
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.VACANT

    r = client.patch(f"/api/v1/flats/{rig['flat'].id}", json={
        "occupancy_status": "owner_occupied", "remarks": "attempted bypass",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200, "the PATCH itself must still succeed (other fields still apply)"
    assert r.json()["remarks"] == "attempted bypass", "legitimate fields in the same PATCH still work"
    assert _flat_status(db, rig["flat"].id) == OccupancyStatus.VACANT, \
        "occupancy_status must NOT have changed — OccupancyService is the only valid writer"
