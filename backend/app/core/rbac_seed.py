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
