"""A Resident/Tenant must file complaints against their own flat only —
the backend forces flat_id/society_id from their actual Resident/Tenant
record and ignores whatever the client sends, closing the gap where any
authenticated member could pick any flat in the society."""
from tests.conftest import make_user, make_society, make_wing, make_flat


def _link_resident(db, user, flat_id, full_name="Res"):
    from app.models.resident import Resident, ResidentType
    r = Resident(
        flat_id=flat_id, user_id=user.id, full_name=full_name,
        resident_type=ResidentType.OWNER, is_primary=True,
    )
    db.add(r); db.commit(); db.refresh(r)
    return r


def _link_tenant(db, user, flat_id, full_name="Ten"):
    from app.models.tenant import Tenant
    t = Tenant(flat_id=flat_id, user_id=user.id, full_name=full_name)
    db.add(t); db.commit(); db.refresh(t)
    return t


def _rig(db):
    from app.models.wing import Wing
    society = make_society(db, "OwnFlat Society")
    wing_a = make_wing(db, society.id, "Wing A")
    wing_b = Wing(society_id=society.id, name="Wing B", code="B")
    db.add(wing_b); db.commit(); db.refresh(wing_b)
    own_flat = make_flat(db, wing_a.id, "A-101")
    other_flat = make_flat(db, wing_b.id, "B-201")
    return society, own_flat, other_flat


def _payload(society_id, flat_id=None, **overrides):
    data = {
        "title": "Leaking tap", "description": "Kitchen tap is leaking.",
        "category": "plumbing", "priority": "medium",
        "society_id": str(society_id),
    }
    if flat_id is not None:
        data["flat_id"] = str(flat_id)
    data.update(overrides)
    return data


def test_resident_complaint_forced_to_own_flat(client, db):
    society, own_flat, other_flat = _rig(db)
    resident = make_user(db, "res-own@cmp.com", role="Resident")
    _link_resident(db, resident["user"], own_flat.id)

    r = client.post("/api/v1/complaints/",
                    json=_payload(society.id, flat_id=other_flat.id),
                    headers=resident["headers"])
    assert r.status_code == 201
    body = r.json()
    assert body["flat_id"] == str(own_flat.id)
    assert body["flat_number"] == "A-101"


def test_resident_cannot_spoof_society_id(client, db):
    society, own_flat, other_flat = _rig(db)
    other_society = make_society(db, "Other Society")
    resident = make_user(db, "res-spoof@cmp.com", role="Resident")
    _link_resident(db, resident["user"], own_flat.id)

    r = client.post("/api/v1/complaints/",
                    json=_payload(other_society.id),
                    headers=resident["headers"])
    assert r.status_code == 201
    assert r.json()["society_id"] == str(society.id)


def test_tenant_complaint_forced_to_own_flat(client, db):
    society, own_flat, other_flat = _rig(db)
    tenant = make_user(db, "ten-own@cmp.com", role="Tenant")
    _link_tenant(db, tenant["user"], own_flat.id)

    r = client.post("/api/v1/complaints/",
                    json=_payload(society.id, flat_id=other_flat.id),
                    headers=tenant["headers"])
    assert r.status_code == 201
    assert r.json()["flat_id"] == str(own_flat.id)


def test_resident_with_no_linked_flat_unaffected(client, db):
    """A Resident-role account with no Resident row (e.g. common-area/general
    complaints today) keeps existing behavior — no flat required."""
    society, own_flat, other_flat = _rig(db)
    resident = make_user(db, "res-unlinked@cmp.com", role="Resident")

    r = client.post("/api/v1/complaints/", json=_payload(society.id),
                    headers=resident["headers"])
    assert r.status_code == 201
    assert r.json()["flat_id"] is None


def test_admin_can_still_file_for_any_flat(client, db):
    """Admin/Committee/Manager/Staff filing on someone's behalf is untouched
    — only accounts linked to their own Resident/Tenant record are locked."""
    society, own_flat, other_flat = _rig(db)
    admin = make_user(db, "admin-any@cmp.com", role="Society Admin")

    r = client.post("/api/v1/complaints/",
                    json=_payload(society.id, flat_id=other_flat.id),
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["flat_id"] == str(other_flat.id)
