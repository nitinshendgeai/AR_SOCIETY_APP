"""
Forms matrix — which top-level screens (mobile drawer items) a role sees.

A second, independent matrix from the permission tiers: confirms the
default grants reproduce the old hardcoded Dart isAdmin/isAdminOrCommittee/
isSecurity/isStaff/isResident drawer logic exactly, that an Admin can edit
a role's visible forms through the /roles/{role_id}/forms API and have the
change reflected immediately in /roles/forms/mine, and that non-admins
cannot edit the matrix (but can read their own granted forms).
"""
from app.core.rbac_seed import FORM_ROLE_GRANTS, default_role_form_codes
from app.models.role import Role
from tests.conftest import make_user


def test_default_grants_match_dashboard_logic(client, db):
    """For every canonical role, GET /roles/form-matrix must report exactly
    the form codes the old hardcoded Dart drawer logic granted it."""
    admin = make_user(db, "formsadmin1@rbac.com", role="Society Admin")

    for role_name in default_role_form_codes():
        make_user(db, f"{role_name.replace(' ', '').lower()}f@rbac.com", role=role_name)

    r = client.get("/api/v1/roles/form-matrix", headers=admin["headers"])
    assert r.status_code == 200, r.text
    matrix = {row["role_name"]: set(row["form_codes"]) for row in r.json()}

    for role_name, expected_codes in default_role_form_codes().items():
        assert matrix.get(role_name) == set(expected_codes), (
            f"{role_name}: expected {sorted(expected_codes)}, got {sorted(matrix.get(role_name, []))}"
        )


def test_gaps_in_old_dashboard_logic_are_preserved_by_default():
    """Locks in the (known, pre-existing) gaps the old Dart boolean logic
    had, so the migration/seed doesn't silently "fix" behavior beyond what
    was asked — Platform Admin, Gym Trainer, and Tenant get only the two
    unconditional items (Visitors, Complaints); nothing gated by
    isAdmin/isAdminOrCommittee/isSecurity/isStaff/isResident (an Admin can
    grant them more explicitly via the Forms Matrix). Manager's gap was
    later deliberately, partially closed: the FMC Manager is who records
    online payment screenshots, so "online_payments" was added to Manager's
    default grants (see FORM_ROLE_GRANTS)."""
    codes_by_role = default_role_form_codes()
    for role_name in ("Platform Admin", "Gym Trainer", "Tenant"):
        assert set(codes_by_role.get(role_name, [])) == {"visitors", "complaints"}, (
            f"{role_name} unexpectedly has default form grants: {codes_by_role.get(role_name)}"
        )
    assert set(codes_by_role.get("Manager", [])) == {"visitors", "complaints", "online_payments"}


def test_visitors_and_complaints_granted_to_every_role():
    codes_by_role = default_role_form_codes()
    for role_name, codes in codes_by_role.items():
        assert "visitors" in codes
        assert "complaints" in codes


def test_list_forms_requires_admin(client, db):
    resident = make_user(db, "formsres1@rbac.com", role="Resident")
    r = client.get("/api/v1/roles/forms", headers=resident["headers"])
    assert r.status_code == 403


def test_list_forms_returns_all_definitions(client, db):
    admin = make_user(db, "formsadmin2@rbac.com", role="Society Admin")
    r = client.get("/api/v1/roles/forms", headers=admin["headers"])
    assert r.status_code == 200
    codes = {f["code"] for f in r.json()}
    assert codes == set(FORM_ROLE_GRANTS.keys())


def test_form_matrix_requires_admin(client, db):
    resident = make_user(db, "formsres2@rbac.com", role="Resident")
    r = client.get("/api/v1/roles/form-matrix", headers=resident["headers"])
    assert r.status_code == 403


def test_non_admin_cannot_edit_forms(client, db):
    resident = make_user(db, "formsres3@rbac.com", role="Resident")
    role = db.query(Role).filter(Role.name == "Resident").first()
    r = client.put(
        f"/api/v1/roles/{role.id}/forms",
        json={"form_codes": ["users_roles"]},
        headers=resident["headers"],
    )
    assert r.status_code == 403


def test_my_forms_returns_default_grants_for_own_role(client, db):
    manager = make_user(db, "formsmgr1@rbac.com", role="Manager")
    r = client.get("/api/v1/roles/forms/mine", headers=manager["headers"])
    assert r.status_code == 200
    # Manager's old gap (only the two unconditional items) was deliberately
    # partially closed by granting "online_payments" — the FMC Manager is
    # who records payment screenshots.
    assert set(r.json()["form_codes"]) == {"visitors", "complaints", "online_payments"}

    resident = make_user(db, "formsres4@rbac.com", role="Resident")
    r2 = client.get("/api/v1/roles/forms/mine", headers=resident["headers"])
    assert r2.status_code == 200
    assert set(r2.json()["form_codes"]) == {"visitors", "complaints", "edit_my_info"}


def test_admin_can_grant_form_and_it_takes_effect_immediately(client, db):
    """Granting Manager the 'staff' form should show up in Manager's own
    /roles/forms/mine — proving the matrix edit is live."""
    admin   = make_user(db, "formsadmin3@rbac.com", role="Society Admin")
    manager = make_user(db, "formsmgr2@rbac.com", role="Manager")

    pre = client.get("/api/v1/roles/forms/mine", headers=manager["headers"])
    assert "staff" not in pre.json()["form_codes"]

    manager_role = db.query(Role).filter(Role.name == "Manager").first()
    current_codes = {rf.form.code for rf in manager_role.role_forms}
    updated_codes = sorted(current_codes | {"staff"})

    put = client.put(
        f"/api/v1/roles/{manager_role.id}/forms",
        json={"form_codes": updated_codes},
        headers=admin["headers"],
    )
    assert put.status_code == 200, put.text
    assert set(put.json()["form_codes"]) == set(updated_codes)

    post = client.get("/api/v1/roles/forms/mine", headers=manager["headers"])
    assert "staff" in post.json()["form_codes"]


def test_admin_can_revoke_form(client, db):
    admin = make_user(db, "formsadmin4@rbac.com", role="Society Admin")
    make_user(db, "formscomm1@rbac.com", role="Committee Chairman")

    committee_role = db.query(Role).filter(Role.name == "Committee Chairman").first()
    original_codes = sorted({rf.form.code for rf in committee_role.role_forms})
    assert "residents" in original_codes

    put = client.put(
        f"/api/v1/roles/{committee_role.id}/forms",
        json={"form_codes": []},
        headers=admin["headers"],
    )
    assert put.status_code == 200
    assert put.json()["form_codes"] == []

    restore = client.put(
        f"/api/v1/roles/{committee_role.id}/forms",
        json={"form_codes": original_codes},
        headers=admin["headers"],
    )
    assert restore.status_code == 200
    assert set(restore.json()["form_codes"]) == set(original_codes)


def test_update_rejects_unknown_form_code(client, db):
    admin = make_user(db, "formsadmin5@rbac.com", role="Society Admin")
    make_user(db, "formsres5@rbac.com", role="Resident")
    role = db.query(Role).filter(Role.name == "Resident").first()
    r = client.put(
        f"/api/v1/roles/{role.id}/forms",
        json={"form_codes": ["not_a_real_form"]},
        headers=admin["headers"],
    )
    assert r.status_code == 422


def test_update_unknown_role_404s(client, db):
    admin = make_user(db, "formsadmin6@rbac.com", role="Society Admin")
    r = client.put(
        "/api/v1/roles/00000000-0000-0000-0000-000000000000/forms",
        json={"form_codes": []},
        headers=admin["headers"],
    )
    assert r.status_code == 404


def test_custom_role_name_gets_zero_default_forms(db):
    custom = Role(name="Totally Custom Role")
    db.add(custom); db.commit()
    db.refresh(custom)
    assert custom.role_forms == []
