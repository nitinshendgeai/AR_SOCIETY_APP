"""permission_matrix

Revision ID: 9a1b2c3d4e5f
Revises: 7c8d9e0f1a2b
Create Date: 2026-09-04

Tables: permissions, role_permissions

Adds the dynamic RBAC permission matrix: a `permissions` table listing the
named access tiers used by app.core.dependencies (admin, admin_committee,
manager_above, supervisor_above, any_staff, security, any_member), and a
`role_permissions` join table granting them to roles.

Seed data below reproduces, EXACTLY, the role grants the old hardcoded
_ROLES_* tuples in app.core.dependencies used to encode — so running this
migration changes zero access-control behavior until an Admin edits the
matrix via the Permission Matrix screen. (Mirrors app.core.rbac_seed,
duplicated here deliberately since migrations must stay self-contained and
not depend on application code that can change later.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '9a1b2c3d4e5f'
down_revision = '7c8d9e0f1a2b'
branch_labels = None
depends_on    = None


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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'permissions' not in existing_tables:
        op.create_table(
            'permissions',
            sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('created_at',  sa.DateTime(), nullable=False),
            sa.Column('updated_at',  sa.DateTime(), nullable=False),
            sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('code',        sa.String(50), nullable=False),
            sa.Column('name',        sa.String(150), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.UniqueConstraint('code', name='uq_permissions_code'),
        )
        op.create_index('ix_permissions_code', 'permissions', ['code'])

    if 'role_permissions' not in existing_tables:
        op.create_table(
            'role_permissions',
            sa.Column('id',            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('created_at',    sa.DateTime(), nullable=False),
            sa.Column('updated_at',    sa.DateTime(), nullable=False),
            sa.Column('is_active',     sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('role_id',       UUID(as_uuid=True), nullable=False),
            sa.Column('permission_id', UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(['role_id'],       ['roles.id'],       ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
        )
        op.create_index('ix_role_permissions_role_id', 'role_permissions', ['role_id'])
        op.create_index('ix_role_permissions_permission_id', 'role_permissions', ['permission_id'])

    from datetime import datetime as _dt

    permissions_table = sa.table(
        'permissions', sa.column('id', UUID(as_uuid=True)), sa.column('code', sa.String),
        sa.column('name', sa.String), sa.column('description', sa.Text),
        sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
        sa.column('is_active', sa.Boolean),
    )
    role_permissions_table = sa.table(
        'role_permissions', sa.column('id', UUID(as_uuid=True)),
        sa.column('role_id', UUID(as_uuid=True)), sa.column('permission_id', UUID(as_uuid=True)),
        sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
        sa.column('is_active', sa.Boolean),
    )
    roles_table = sa.table('roles', sa.column('id', UUID(as_uuid=True)), sa.column('name', sa.String))

    # ── Seed the 7 permission rows (idempotent) ──────────────────────────────
    now = _dt.utcnow()
    existing_codes = {row[0] for row in bind.execute(sa.select(permissions_table.c.code))}
    to_insert = [
        {"id": uuid.uuid4(), "code": code, "name": name, "description": desc,
         "created_at": now, "updated_at": now, "is_active": True}
        for code, name, desc in PERMISSION_DEFINITIONS
        if code not in existing_codes
    ]
    if to_insert:
        bind.execute(permissions_table.insert(), to_insert)

    # ── Grant each permission to the roles that hold it today (idempotent) ──
    permission_ids = {
        row[1]: row[0]
        for row in bind.execute(sa.select(permissions_table.c.id, permissions_table.c.code))
    }
    existing_grants = {
        (row[0], row[1])
        for row in bind.execute(sa.select(role_permissions_table.c.role_id, role_permissions_table.c.permission_id))
    }
    all_roles = bind.execute(sa.select(roles_table.c.id, roles_table.c.name)).fetchall()

    grants_to_insert = []
    for role_id, role_name in all_roles:
        for code, granted_roles in PERMISSION_ROLE_GRANTS.items():
            if role_name not in granted_roles:
                continue
            permission_id = permission_ids.get(code)
            if not permission_id or (role_id, permission_id) in existing_grants:
                continue
            grants_to_insert.append({
                "id": uuid.uuid4(), "role_id": role_id, "permission_id": permission_id,
                "created_at": now, "updated_at": now, "is_active": True,
            })

    if grants_to_insert:
        bind.execute(role_permissions_table.insert(), grants_to_insert)


def downgrade() -> None:
    op.drop_table('role_permissions')
    op.drop_table('permissions')
