"""checklist_templates_form

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-04

Registers the "checklist_templates" screen in the forms navigation matrix
(see b2c3d4e5f6a7_forms_matrix.py) so the new Checklist Templates admin
screen is reachable from the drawer, and grants it by default to Society
Admin + all Committee roles — the same default as the "Staff" and
"Parking Management" screens it sits alongside.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

revision      = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on    = None

FORM_CODE = "checklist_templates"
FORM_NAME = "Checklist Templates"
FORM_DESC = "Department-scoped reusable duty checklists"

_ADMIN_OR_COMMITTEE_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member",
)


def upgrade() -> None:
    bind = op.get_bind()
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

    existing = bind.execute(
        sa.select(forms_table.c.id).where(forms_table.c.code == FORM_CODE)
    ).first()
    if existing:
        form_id = existing[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(forms_table.insert(), [{
            "id": form_id, "code": FORM_CODE, "name": FORM_NAME, "description": FORM_DESC,
            "created_at": now, "updated_at": now, "is_active": True,
        }])

    existing_grants = {
        row[0] for row in bind.execute(
            sa.select(role_forms_table.c.role_id).where(role_forms_table.c.form_id == form_id)
        )
    }
    all_roles = bind.execute(
        sa.select(roles_table.c.id, roles_table.c.name)
        .where(roles_table.c.name.in_(_ADMIN_OR_COMMITTEE_ROLES))
    ).fetchall()

    grants_to_insert = [
        {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id,
         "created_at": now, "updated_at": now, "is_active": True}
        for role_id, _ in all_roles if role_id not in existing_grants
    ]
    if grants_to_insert:
        bind.execute(role_forms_table.insert(), grants_to_insert)


def downgrade() -> None:
    bind = op.get_bind()
    forms_table = sa.table('forms', sa.column('id', UUID(as_uuid=True)), sa.column('code', sa.String))
    row = bind.execute(sa.select(forms_table.c.id).where(forms_table.c.code == FORM_CODE)).first()
    if row:
        role_forms_table = sa.table('role_forms', sa.column('form_id', UUID(as_uuid=True)))
        bind.execute(role_forms_table.delete().where(role_forms_table.c.form_id == row[0]))
        bind.execute(forms_table.delete().where(forms_table.c.id == row[0]))
