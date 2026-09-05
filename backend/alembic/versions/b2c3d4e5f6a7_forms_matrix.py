"""forms_matrix

Revision ID: b2c3d4e5f6a7
Revises: 9a1b2c3d4e5f
Create Date: 2026-09-04

Tables: forms, role_forms

Adds a second, independent matrix from the permission tiers added in
9a1b2c3d4e5f: which top-level navigable screens (the mobile drawer items)
a role can see. `forms` lists the screens; `role_forms` grants them to
roles.

Seed data below reproduces, EXACTLY, the boolean logic
_visibleMenuItems() in mobile/lib/features/dashboard/role_dashboards.dart
used to hardcode (isAdmin / isAdminOrCommittee / isSecurity / isStaff /
isResident from UserEntity) — so running this migration changes zero
navigation behavior until an Admin edits the matrix via the Forms Matrix
screen. (Mirrors app.core.rbac_seed, duplicated here deliberately since
migrations must stay self-contained and not depend on application code
that can change later.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

revision      = 'b2c3d4e5f6a7'
down_revision = '9a1b2c3d4e5f'
branch_labels = None
depends_on    = None


FORM_DEFINITIONS = [
    ("residents",                "Residents",                "Resident master records"),
    ("tenants",                  "Tenants",                  "Tenant master records"),
    ("users_roles",              "Users & Roles",             "User account and role assignment management"),
    ("permission_matrix",        "Permission Matrix",         "Edit which access tiers each role is granted"),
    ("forms_matrix",             "Forms Matrix",              "Edit which navigation screens each role is granted"),
    ("society_settings",         "Society Settings",          "Society profile and configuration"),
    ("visitors",                 "Visitors",                  "Visitor log and approvals"),
    ("complaints",               "Complaints",                "Complaint tracking"),
    ("edit_my_info",             "Edit My Info",              "Resident self-service profile edit request"),
    ("pending_resident_changes", "Pending Resident Changes",  "Review queue for resident self-service edits"),
    ("staff",                    "Staff",                     "Staff master records, duties, and attendance"),
    ("parking_management",       "Parking Management",        "Parking zones, slots, and allocations"),
    ("setup_wizard",             "Setup Wizard",               "Society structure setup wizard"),
]

_PLATFORM    = ("Platform Admin",)
_SOCIETY     = ("Society Admin",)
_COMMITTEE   = ("Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member")
_MANAGER     = ("Manager",)
_SUPERVISORS = ("Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor")
_STAFF       = ("Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer")
_RESIDENTS   = ("Resident", "Tenant")
_ALL_CANONICAL_ROLES = (*_PLATFORM, *_SOCIETY, *_COMMITTEE, *_MANAGER, *_SUPERVISORS, *_STAFF, *_RESIDENTS)

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

FORM_ROLE_GRANTS = {
    "residents":                _ADMIN_OR_COMMITTEE_ROLES,
    "tenants":                  _ADMIN_OR_COMMITTEE_ROLES,
    "users_roles":              _ADMIN_ONLY_ROLES,
    "permission_matrix":        _ADMIN_ONLY_ROLES,
    "forms_matrix":             _ADMIN_ONLY_ROLES,
    "society_settings":         _ADMIN_OR_COMMITTEE_ROLES,
    "visitors":                 _ALL_CANONICAL_ROLES,
    "complaints":               _ALL_CANONICAL_ROLES,
    "edit_my_info":             _RESIDENT_ONLY_ROLE,
    "pending_resident_changes": _ADMIN_OR_COMMITTEE_ROLES,
    "staff":                    tuple(sorted(set(_ADMIN_OR_COMMITTEE_ROLES) | set(_SECURITY_DASH_ROLES) | set(_STAFF_DASH_ROLES))),
    "parking_management":       _ADMIN_OR_COMMITTEE_ROLES,
    "setup_wizard":             _ADMIN_OR_COMMITTEE_ROLES,
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'forms' not in existing_tables:
        op.create_table(
            'forms',
            sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('created_at',  sa.DateTime(), nullable=False),
            sa.Column('updated_at',  sa.DateTime(), nullable=False),
            sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('code',        sa.String(50), nullable=False),
            sa.Column('name',        sa.String(150), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.UniqueConstraint('code', name='uq_forms_code'),
        )
        op.create_index('ix_forms_code', 'forms', ['code'])

    if 'role_forms' not in existing_tables:
        op.create_table(
            'role_forms',
            sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('role_id',    UUID(as_uuid=True), nullable=False),
            sa.Column('form_id',    UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('role_id', 'form_id', name='uq_role_form'),
        )
        op.create_index('ix_role_forms_role_id', 'role_forms', ['role_id'])
        op.create_index('ix_role_forms_form_id', 'role_forms', ['form_id'])

    now = datetime.utcnow()

    forms_table = sa.table(
        'forms', sa.column('id', UUID(as_uuid=True)), sa.column('code', sa.String),
        sa.column('name', sa.String), sa.column('description', sa.Text),
        sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
        sa.column('is_active', sa.Boolean),
    )
    role_forms_table = sa.table(
        'role_forms', sa.column('id', UUID(as_uuid=True)),
        sa.column('role_id', UUID(as_uuid=True)), sa.column('form_id', UUID(as_uuid=True)),
        sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
        sa.column('is_active', sa.Boolean),
    )
    roles_table = sa.table('roles', sa.column('id', UUID(as_uuid=True)), sa.column('name', sa.String))

    # ── Seed the form rows (idempotent) ──────────────────────────────────────
    existing_codes = {row[0] for row in bind.execute(sa.select(forms_table.c.code))}
    to_insert = [
        {"id": uuid.uuid4(), "code": code, "name": name, "description": desc,
         "created_at": now, "updated_at": now, "is_active": True}
        for code, name, desc in FORM_DEFINITIONS
        if code not in existing_codes
    ]
    if to_insert:
        bind.execute(forms_table.insert(), to_insert)

    # ── Grant each form to the roles that see it today (idempotent) ─────────
    form_ids = {
        row[1]: row[0]
        for row in bind.execute(sa.select(forms_table.c.id, forms_table.c.code))
    }
    existing_grants = {
        (row[0], row[1])
        for row in bind.execute(sa.select(role_forms_table.c.role_id, role_forms_table.c.form_id))
    }
    all_roles = bind.execute(sa.select(roles_table.c.id, roles_table.c.name)).fetchall()

    grants_to_insert = []
    for role_id, role_name in all_roles:
        for code, granted_roles in FORM_ROLE_GRANTS.items():
            if role_name not in granted_roles:
                continue
            form_id = form_ids.get(code)
            if not form_id or (role_id, form_id) in existing_grants:
                continue
            grants_to_insert.append({
                "id": uuid.uuid4(), "role_id": role_id, "form_id": form_id,
                "created_at": now, "updated_at": now, "is_active": True,
            })

    if grants_to_insert:
        bind.execute(role_forms_table.insert(), grants_to_insert)


def downgrade() -> None:
    op.drop_table('role_forms')
    op.drop_table('forms')
