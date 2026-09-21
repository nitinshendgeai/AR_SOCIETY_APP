"""
Dynamic RBAC permission matrix — Permission / RolePermission.

Confirms the DB-driven guards in app.core.dependencies reproduce the old
hardcoded _ROLES_* tuple behavior exactly by default, that an Admin can
edit a role's permissions through the /roles/{role_id}/permissions API and
have the change take effect immediately, and that non-admins cannot touch
the matrix.
"""
from app.core.rbac_seed import PERMISSION_ROLE_GRANTS, default_role_permission_codes
from app.models.role import Role
from tests.conftest import make_user


def test_default_grants_match_canonical_role_sets(client, db):
    """For every canonical role, GET /roles/permission-matrix must report
    exactly the permission codes the old hardcoded tuples granted it —
    proving the migration/auto-grant seed changed zero behavior."""
    admin = make_user(db, "matrixadmin1@rbac.com", role="Society Admin")

    # Touch every canonical role so its Role row (and auto-granted
    # permissions) exists in this test's DB.
    for role_name in default_role_permission_codes():
        make_user(db, f"{role_name.replace(' ', '').lower()}@rbac.com", role=role_name)

    r = client.get("/api/v1/roles/permission-matrix", headers=admin["headers"])
    assert r.status_code == 200, r.text
    matrix = {row["role_name"]: set(row["permission_codes"]) for row in r.json()}

    for role_name, expected_codes in default_role_permission_codes().items():
        assert matrix.get(role_name) == set(expected_codes), (
            f"{role_name}: expected {sorted(expected_codes)}, got {sorted(matrix.get(role_name, []))}"
        )


def test_guard_tiers_match_grants_for_every_role():
    """Sanity check the seed data itself: every role named in a tier's grant
    list must resolve back to that tier when the matrix is inverted."""
    codes_by_role = default_role_permission_codes()
    for code, roles in PERMISSION_ROLE_GRANTS.items():
        for role_name in roles:
            assert code in codes_by_role[role_name]


def test_list_permissions_requires_admin(client, db):
    resident = make_user(db, "matrixres1@rbac.com", role="Resident")
    r = client.get("/api/v1/roles/permissions", headers=resident["headers"])
    assert r.status_code == 403


def test_list_permissions_returns_seven_tiers(client, db):
    admin = make_user(db, "matrixadmin2@rbac.com", role="Society Admin")
    r = client.get("/api/v1/roles/permissions", headers=admin["headers"])
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert codes == set(PERMISSION_ROLE_GRANTS.keys())


def test_permission_matrix_requires_admin(client, db):
    resident = make_user(db, "matrixres2@rbac.com", role="Resident")
    r = client.get("/api/v1/roles/permission-matrix", headers=resident["headers"])
    assert r.status_code == 403


def test_non_admin_cannot_edit_permissions(client, db):
    resident = make_user(db, "matrixres3@rbac.com", role="Resident")
    role = db.query(Role).filter(Role.name == "Resident").first()
    r = client.put(
        f"/api/v1/roles/{role.id}/permissions",
        json={"permission_codes": ["admin"]},
        headers=resident["headers"],
    )
    assert r.status_code == 403


def test_admin_can_grant_new_permission_and_it_takes_effect_immediately(client, db):
    """Granting Manager the 'admin' tier should let a Manager user pass
    require_admin — proving the matrix edit is live, not just cosmetic."""
    admin   = make_user(db, "matrixadmin3@rbac.com", role="Society Admin")
    manager = make_user(db, "matrixmgr1@rbac.com", role="Manager")

    # Before the grant: Manager does not satisfy require_admin.
    pre = client.get("/api/v1/users/admin/dashboard", headers=manager["headers"])
    assert pre.status_code == 403

    manager_role = db.query(Role).filter(Role.name == "Manager").first()
    current_codes = {rp.permission.code for rp in manager_role.role_permissions}
    updated_codes = sorted(current_codes | {"admin"})

    put = client.put(
        f"/api/v1/roles/{manager_role.id}/permissions",
        json={"permission_codes": updated_codes},
        headers=admin["headers"],
    )
    assert put.status_code == 200, put.text
    assert set(put.json()["permission_codes"]) == set(updated_codes)

    post = client.get("/api/v1/users/admin/dashboard", headers=manager["headers"])
    assert post.status_code == 200


def test_admin_can_revoke_permission_and_it_takes_effect_immediately(client, db):
    """Revoking 'any_staff' from Security Staff should make it fail
    require_any_staff-gated endpoints, and restoring it should undo that."""
    admin   = make_user(db, "matrixadmin4@rbac.com", role="Society Admin")
    guard   = make_user(db, "matrixguard1@rbac.com", role="Security Staff")

    security_role = db.query(Role).filter(Role.name == "Security Staff").first()
    original_codes = sorted({rp.permission.code for rp in security_role.role_permissions})
    assert "any_staff" in original_codes

    # Revoke everything.
    put = client.put(
        f"/api/v1/roles/{security_role.id}/permissions",
        json={"permission_codes": []},
        headers=admin["headers"],
    )
    assert put.status_code == 200
    assert put.json()["permission_codes"] == []

    denied = client.get(
        f"/api/v1/staff/attendance/{guard['user'].id}", headers=guard["headers"]
    )
    assert denied.status_code == 403

    # Restore.
    restore = client.put(
        f"/api/v1/roles/{security_role.id}/permissions",
        json={"permission_codes": original_codes},
        headers=admin["headers"],
    )
    assert restore.status_code == 200
    assert set(restore.json()["permission_codes"]) == set(original_codes)


def test_update_rejects_unknown_permission_code(client, db):
    admin = make_user(db, "matrixadmin5@rbac.com", role="Society Admin")
    make_user(db, "matrixres4@rbac.com", role="Resident")
    role = db.query(Role).filter(Role.name == "Resident").first()
    r = client.put(
        f"/api/v1/roles/{role.id}/permissions",
        json={"permission_codes": ["not_a_real_code"]},
        headers=admin["headers"],
    )
    assert r.status_code == 422


def test_update_unknown_role_404s(client, db):
    admin = make_user(db, "matrixadmin6@rbac.com", role="Society Admin")
    r = client.put(
        "/api/v1/roles/00000000-0000-0000-0000-000000000000/permissions",
        json={"permission_codes": []},
        headers=admin["headers"],
    )
    assert r.status_code == 404


def test_custom_role_name_gets_zero_default_permissions(db):
    """A role name that never matched any old hardcoded _ROLES_* tuple must
    still be granted nothing by default — the auto-grant listener must not
    over-grant on names it doesn't recognize."""
    custom = Role(name="Totally Custom Role")
    db.add(custom); db.commit()
    db.refresh(custom)
    assert custom.role_permissions == []
