"""
Canonical seed data + auto-provisioning for the dynamic RBAC permission
matrix (Permission / RolePermission).

Each permission code corresponds 1:1 to a guard function in
app.core.dependencies (require_<code>). PERMISSION_ROLE_GRANTS reproduces,
EXACTLY, the role grants the old hardcoded _ROLES_* tuples in
dependencies.py used to encode before the guards became DB-driven — so
seeding this data changes zero access-control behavior until an Admin
edits the matrix via the Permission Matrix screen.

The after_insert listener below means every Role row — however and
wherever it's created (onboarding, the dev seed script, a test's
make_user() helper) — is automatically granted the permissions a canonical
role of that name has always implicitly had. Non-canonical role names get
no grants, matching the pre-dynamic-RBAC behavior where such names never
matched any _ROLES_* tuple either.
"""
from sqlalchemy import event, select
from app.models.role import Role
from app.models.permission import Permission, RolePermission
from app.models.form import Form, RoleForm

PERMISSION_DEFINITIONS = [
    ("admin",            "Admin",                "Full society/platform administration"),
    ("admin_committee",  "Admin + Committee",     "Admin plus all committee roles"),
    ("manager_above",    "Manager and above",     "Admin, committee, and manager"),
    ("supervisor_above", "Supervisor and above",  "Manager-and-above plus department supervisors"),
    ("any_staff",        "Any Staff",             "Supervisor-and-above plus all staff roles"),
    ("security",         "Security",              "Admin, committee, manager, and the security department only"),
    ("any_member",       "Any Member",            "Everyone, including residents and tenants"),
]

_PLATFORM    = ("Platform Admin",)
_SOCIETY     = ("Society Admin",)
_COMMITTEE   = ("Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member")
_MANAGER     = ("Manager",)
_SUPERVISORS = ("Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor")
_STAFF       = ("Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer")
_RESIDENTS   = ("Resident", "Tenant")

PERMISSION_ROLE_GRANTS = {
    "admin":            (*_PLATFORM, *_SOCIETY),
    "admin_committee":  (*_PLATFORM, *_SOCIETY, *_COMMITTEE),
    "manager_above":    (*_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER),
    "supervisor_above": (*_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER, *_SUPERVISORS),
    "any_staff":        (*_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER, *_SUPERVISORS, *_STAFF),
    "security":         (*_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER, "Security Supervisor", "Security Staff"),
    "any_member":       (*_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER, *_SUPERVISORS, *_STAFF, *_RESIDENTS),
}


def default_role_permission_codes() -> dict:
    """{role_name: [permission_code, ...]} derived from PERMISSION_ROLE_GRANTS."""
    result: dict = {}
    for code, roles in PERMISSION_ROLE_GRANTS.items():
        for role_name in roles:
            result.setdefault(role_name, []).append(code)
    return result


def seed_permission_definitions(connection) -> None:
    """Idempotently insert the canonical Permission rows. Safe to call
    against a bare/empty permissions table — e.g. the pytest SQLite
    bootstrap, which builds schema straight from the models rather than
    running Alembic migrations."""
    table = Permission.__table__
    existing = {row.code for row in connection.execute(select(table.c.code))}
    missing = [
        {"code": code, "name": name, "description": desc}
        for code, name, desc in PERMISSION_DEFINITIONS
        if code not in existing
    ]
    if missing:
        connection.execute(table.insert(), missing)


@event.listens_for(Role, "after_insert")
def _autogrant_default_permissions(mapper, connection, target: Role) -> None:
    codes = default_role_permission_codes().get(target.name)
    if not codes:
        return

    perm_table = Permission.__table__
    perm_ids = [
        row.id for row in connection.execute(
            select(perm_table.c.id).where(perm_table.c.code.in_(codes))
        )
    ]
    if not perm_ids:
        return  # permissions table not seeded yet

    rp_table = RolePermission.__table__
    connection.execute(
        rp_table.insert(),
        [{"role_id": target.id, "permission_id": pid} for pid in perm_ids],
    )


# ── Forms (top-level navigable screens) matrix ───────────────────────────────
#
# A second, independent matrix from the permission tiers above: which
# top-level screens (the mobile drawer's navigation items) a role can see.
# FORM_ROLE_GRANTS reproduces, EXACTLY, the boolean logic
# _visibleMenuItems() in mobile/lib/features/dashboard/role_dashboards.dart
# used to hardcode (isAdmin / isAdminOrCommittee / isSecurity / isStaff /
# isResident, as defined in UserEntity — note these use the SAME literal
# role-name / substring checks the Dart code used, including their existing
# gaps: "Platform Admin" never matched isAdmin's exact-string check, and
# "Manager"/"Gym Trainer" never matched isStaff's "Staff"/"Supervisor"
# substring check, so those roles see nothing gated by default here either.
# An Admin can now close those gaps from the Forms Matrix screen without a
# code change.

FORM_DEFINITIONS = [
    ("residents",                 "Residents",                 "Resident master records"),
    ("tenants",                   "Tenants",                   "Tenant master records"),
    ("users_roles",               "Users & Roles",              "User account and role assignment management"),
    ("permission_matrix",         "Permission Matrix",          "Edit which access tiers each role is granted"),
    ("forms_matrix",              "Forms Matrix",                "Edit which navigation screens each role is granted"),
    ("society_settings",          "Society Settings",           "Society profile and configuration"),
    ("visitors",                  "Visitors",                   "Visitor log and approvals"),
    ("complaints",                "Complaints",                 "Complaint tracking"),
    ("edit_my_info",              "Edit My Info",                "Resident self-service profile edit request"),
    ("pending_resident_changes",  "Pending Resident Changes",   "Review queue for resident self-service edits"),
    ("staff",                     "Staff",                      "Staff master records, duties, and attendance"),
    ("parking_management",        "Parking Management",        "Parking zones, slots, and allocations"),
    ("setup_wizard",              "Setup Wizard",                "Society structure setup wizard"),
]

_ADMIN_OR_COMMITTEE_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member",
)
_ADMIN_ONLY_ROLES = ("Society Admin",)
_SECURITY_DASH_ROLES = ("Security Supervisor", "Security Staff")
_STAFF_DASH_ROLES = (
    "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
    "Security Staff", "Housekeeping Staff", "Technical Staff",
)
_RESIDENT_ONLY_ROLE = ("Resident",)
# All 16 canonical roles — reuses the tuples already defined above for the
# permission-tier matrix rather than re-listing or importing them, so the
# two matrices can't drift out of sync with EXTENDED_DEFAULT_ROLES.
_ALL_CANONICAL_ROLES = (
    *_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER,
    *_SUPERVISORS, *_STAFF, *_RESIDENTS,
)

FORM_ROLE_GRANTS = {
    "residents":                _ADMIN_OR_COMMITTEE_ROLES,
    "tenants":                  _ADMIN_OR_COMMITTEE_ROLES,
    "users_roles":              _ADMIN_ONLY_ROLES,
    "permission_matrix":        _ADMIN_ONLY_ROLES,
    "forms_matrix":             _ADMIN_ONLY_ROLES,
    "society_settings":         _ADMIN_OR_COMMITTEE_ROLES,
    "visitors":                 _ALL_CANONICAL_ROLES,
    "complaints":                _ALL_CANONICAL_ROLES,
    "edit_my_info":             _RESIDENT_ONLY_ROLE,
    "pending_resident_changes": _ADMIN_OR_COMMITTEE_ROLES,
    "staff":                    tuple(sorted(set(_ADMIN_OR_COMMITTEE_ROLES) | set(_SECURITY_DASH_ROLES) | set(_STAFF_DASH_ROLES))),
    "parking_management":       _ADMIN_OR_COMMITTEE_ROLES,
    "setup_wizard":             _ADMIN_OR_COMMITTEE_ROLES,
}


def default_role_form_codes() -> dict:
    """{role_name: [form_code, ...]} derived from FORM_ROLE_GRANTS."""
    result: dict = {}
    for code, roles in FORM_ROLE_GRANTS.items():
        for role_name in roles:
            result.setdefault(role_name, []).append(code)
    return result


def seed_form_definitions(connection) -> None:
    """Idempotently insert the canonical Form rows (mirrors
    seed_permission_definitions — see its docstring)."""
    table = Form.__table__
    existing = {row.code for row in connection.execute(select(table.c.code))}
    missing = [
        {"code": code, "name": name, "description": desc}
        for code, name, desc in FORM_DEFINITIONS
        if code not in existing
    ]
    if missing:
        connection.execute(table.insert(), missing)


@event.listens_for(Role, "after_insert")
def _autogrant_default_forms(mapper, connection, target: Role) -> None:
    codes = default_role_form_codes().get(target.name)
    if not codes:
        return

    form_table = Form.__table__
    form_ids = [
        row.id for row in connection.execute(
            select(form_table.c.id).where(form_table.c.code.in_(codes))
        )
    ]
    if not form_ids:
        return  # forms table not seeded yet

    rf_table = RoleForm.__table__
    connection.execute(
        rf_table.insert(),
        [{"role_id": target.id, "form_id": fid} for fid in form_ids],
    )
