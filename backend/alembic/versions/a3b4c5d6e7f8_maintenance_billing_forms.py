"""maintenance_billing_forms

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-24

Registers two screens in the forms navigation matrix (same pattern as
f6a7b8c9d0e1_online_payments_form.py): "maintenance_billing" for the
society side (Society Admin, all Committee roles, Manager) and "my_bills"
for Residents viewing their own flat's bills.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

revision      = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on    = None

FORMS = (
    ("maintenance_billing", "Maintenance Billing",
     "Charge heads, billing cycles, and generating/issuing flat maintenance bills",
     ("Society Admin", "Committee Chairman", "Committee Secretary",
      "Committee Treasurer", "Committee Member", "Manager")),
    ("my_bills", "My Bills",
     "Resident view of their own flat's maintenance bills",
     ("Resident",)),
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

    for code, name, desc, granted_roles in FORMS:
        existing = bind.execute(
            sa.select(forms_table.c.id).where(forms_table.c.code == code)
        ).first()
        if existing:
            form_id = existing[0]
        else:
            form_id = uuid.uuid4()
            bind.execute(forms_table.insert(), [{
                "id": form_id, "code": code, "name": name, "description": desc,
                "created_at": now, "updated_at": now, "is_active": True,
            }])

        existing_grants = {
            row[0] for row in bind.execute(
                sa.select(role_forms_table.c.role_id).where(role_forms_table.c.form_id == form_id)
            )
        }
        roles = bind.execute(
            sa.select(roles_table.c.id, roles_table.c.name)
            .where(roles_table.c.name.in_(granted_roles))
        ).fetchall()
        grants_to_insert = [
            {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id,
             "created_at": now, "updated_at": now, "is_active": True}
            for role_id, _ in roles if role_id not in existing_grants
        ]
        if grants_to_insert:
            bind.execute(role_forms_table.insert(), grants_to_insert)


def downgrade() -> None:
    bind = op.get_bind()
    forms_table = sa.table('forms', sa.column('id', UUID(as_uuid=True)), sa.column('code', sa.String))
    role_forms_table = sa.table('role_forms', sa.column('form_id', UUID(as_uuid=True)))
    for code, *_ in FORMS:
        row = bind.execute(sa.select(forms_table.c.id).where(forms_table.c.code == code)).first()
        if row:
            bind.execute(role_forms_table.delete().where(role_forms_table.c.form_id == row[0]))
            bind.execute(forms_table.delete().where(forms_table.c.id == row[0]))
