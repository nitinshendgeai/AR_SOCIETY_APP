"""
Agreement lifecycle — Phase M1.3.

Covers: creation via tenant move-in, renewal (renewal_of_id linkage,
history preservation, cross-society/cross-tenant/cross-flat rejection,
overlap rejection), termination via move-out, audit entries.
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
    society = make_society(db, "Agreement Test Society")
    admin = make_user(db, "agradm@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing AG1")
    flat = make_flat(db, wing.id, "AG-101")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


def _create_active_tenant(client, rig, rent="15000.00"):
    start = date.today()
    end = start + timedelta(days=180)
    return client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Agreement Tenant",
        "agreement_start_date": str(start), "agreement_end_date": str(end),
        "monthly_rent": rent, "move_in_date": str(start),
    }, headers=rig["admin"]["headers"]).json(), start, end


def test_agreement_created_on_move_in(client, db, rig):
    from app.models.agreement_tracker import AgreementTracker, AgreementStatus
    tenant, start, end = _create_active_tenant(client, rig)
    agr = db.query(AgreementTracker).filter(
        AgreementTracker.id == _to_uuid(tenant["active_agreement_id"])).first()
    assert agr.status == AgreementStatus.ACTIVE
    assert agr.tenant_id == _to_uuid(tenant["id"])
    assert agr.flat_id == rig["flat"].id


def test_agreement_society_correctly_assigned(client, db, rig):
    """Regression coverage for the P0 AgreementTracker.society_id=None
    bug (Phase M1 audit / Phase M1 P0 fix) — re-verified through the new
    Tenant-creation path rather than only the direct occupancy endpoint."""
    tenant, _, _ = _create_active_tenant(client, rig)
    from app.models.agreement_tracker import AgreementTracker
    agr = db.query(AgreementTracker).filter(
        AgreementTracker.id == _to_uuid(tenant["active_agreement_id"])).first()
    assert agr.society_id is not None
    assert agr.society_id == rig["society"].id


def test_renewal_creates_new_agreement_linked_to_previous(client, db, rig):
    from app.models.agreement_tracker import AgreementTracker, AgreementStatus
    tenant, start, end = _create_active_tenant(client, rig)
    old_agr_id = tenant["active_agreement_id"]

    new_start = end
    new_end = end + timedelta(days=180)
    r = client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(new_start), "end_date": str(new_end),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 201, r.text
    new_agr = r.json()

    assert new_agr["renewal_of_id"] == old_agr_id
    assert new_agr["status"] == "active"
    assert new_agr["id"] != old_agr_id

    old_agr = db.query(AgreementTracker).filter(AgreementTracker.id == _to_uuid(old_agr_id)).first()
    assert old_agr.status == AgreementStatus.RENEWED, "old agreement must be preserved, not deleted"


def test_renewal_preserves_old_agreement_row(client, db, rig):
    from app.models.agreement_tracker import AgreementTracker
    tenant, start, end = _create_active_tenant(client, rig)
    old_agr_id = tenant["active_agreement_id"]

    before_count = db.query(AgreementTracker).filter(AgreementTracker.tenant_id == _to_uuid(tenant["id"])).count()
    client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end + timedelta(days=90)),
    }, headers=rig["admin"]["headers"])
    after_count = db.query(AgreementTracker).filter(AgreementTracker.tenant_id == _to_uuid(tenant["id"])).count()

    assert after_count == before_count + 1, "renewal must ADD a row, never delete the old one"
    still_exists = db.query(AgreementTracker).filter(AgreementTracker.id == _to_uuid(old_agr_id)).first()
    assert still_exists is not None


def test_renewal_carries_over_terms_when_not_specified(client, db, rig):
    tenant, start, end = _create_active_tenant(client, rig, rent="15000.00")
    r = client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end + timedelta(days=90)),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 201
    assert r.json()["monthly_rent"] == "15000.00", "should carry over the prior agreement's rent when not overridden"


def test_renewal_updates_tenant_cached_terms(client, db, rig):
    tenant, start, end = _create_active_tenant(client, rig, rent="15000.00")
    new_start, new_end = end, end + timedelta(days=90)
    client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(new_start), "end_date": str(new_end), "monthly_rent": "18000.00",
    }, headers=rig["admin"]["headers"])
    updated = client.get(f"/api/v1/tenants/{tenant['id']}", headers=rig["admin"]["headers"]).json()
    assert updated["agreement_start_date"] == str(new_start)
    assert updated["agreement_end_date"] == str(new_end)
    assert updated["monthly_rent"] == "18000.00"


def test_invalid_renewal_end_before_start_rejected(client, db, rig):
    tenant, start, end = _create_active_tenant(client, rig)
    r = client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end - timedelta(days=1)),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 422


def test_renewal_with_no_active_agreement_rejected(client, db, rig):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Never Moved In Tenant",
    }, headers=rig["admin"]["headers"]).json()
    r = client.post(f"/api/v1/tenants/{created['id']}/renew-agreement", json={
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=90)),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 409


def test_overlapping_renewal_rejected(client, db, rig):
    """A renewal whose dates overlap a DIFFERENT active agreement on the
    same flat must be rejected — constructed directly since the tenant
    move-in flow itself already prevents two simultaneously-active tenants
    on one flat (so this exercises the renewal's own overlap guard)."""
    from app.models.agreement_tracker import AgreementTracker, AgreementStatus
    tenant, start, end = _create_active_tenant(client, rig)

    # A second, independently-active agreement on the same flat (simulating
    # a data state the renewal overlap-check must still catch).
    other_agr = AgreementTracker(
        society_id=rig["society"].id, flat_id=rig["flat"].id, tenant_id=_to_uuid(tenant["id"]),
        start_date=end + timedelta(days=1), end_date=end + timedelta(days=100),
        status=AgreementStatus.ACTIVE,
    )
    db.add(other_agr); db.commit()

    r = client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end + timedelta(days=50)),  # overlaps other_agr
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 409


def test_cross_society_renewal_rejected(client, db, rig):
    society_b = make_society(db, "Agreement Society B")
    admin_b = make_user(db, "agradmB@test.com", role="Society Admin")
    _set_society(db, admin_b["user"], society_b.id)

    tenant, start, end = _create_active_tenant(client, rig)
    r = client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end + timedelta(days=90)),
    }, headers=admin_b["headers"])
    assert r.status_code == 404, "a different society's admin must not be able to renew this tenant's agreement"


def test_move_out_terminates_agreement_correctly(client, db, rig):
    from app.models.agreement_tracker import AgreementTracker, AgreementStatus
    tenant, start, end = _create_active_tenant(client, rig)
    agr_id = tenant["active_agreement_id"]

    r = client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(rig["flat"].id), "tenant_id": tenant["id"],
        "move_out_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200

    agr = db.query(AgreementTracker).filter(AgreementTracker.id == _to_uuid(agr_id)).first()
    assert agr.status == AgreementStatus.TERMINATED
    assert agr.termination_reason is not None


def test_audit_entries_generated_for_agreement_create_and_renew(client, db, rig):
    from app.models.audit_log import AuditLog
    tenant, start, end = _create_active_tenant(client, rig)
    create_entries = db.query(AuditLog).filter(
        AuditLog.entity_type == "AgreementTracker",
        AuditLog.entity_id == tenant["active_agreement_id"],
    ).all()
    assert len(create_entries) >= 1, "agreement creation must be audited"

    client.post(f"/api/v1/tenants/{tenant['id']}/renew-agreement", json={
        "start_date": str(end), "end_date": str(end + timedelta(days=90)),
    }, headers=rig["admin"]["headers"])
    renewal_entries = db.query(AuditLog).filter(AuditLog.module == "agreement").all()
    # 1 for initial creation + 1 for old->renewed + 1 for new agreement creation
    assert len(renewal_entries) >= 3
