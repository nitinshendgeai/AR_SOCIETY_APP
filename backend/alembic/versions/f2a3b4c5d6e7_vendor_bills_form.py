"""vendor_bills_form

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-23

Registers the "vendor_bills" screen in the forms navigation matrix (see
f6a7b8c9d0e1_online_payments_form.py for the identical pattern) so the
new vendor-invoice/payment screen is reachable from the drawer, granted
by default to the same roles as Online Payments and Bank Reconciliation:
Society Admin, all Committee roles, and Manager.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

revision      = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on    = None

FORM_CODE = "vendor_bills"
FORM_NAME = "Vendor Bills"
FORM_DESC = "Vendor invoices and payments made against them"

_GRANTED_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member", "Manager",
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
        .where(roles_table.c.name.in_(_GRANTED_ROLES))
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
