"""maintenance_elements

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-24

Maintenance element master: a per-society, editable list of the kinds of
charge a society levies (seeded with the standard bye-law elements on
first use by the app, not here — see standard_elements.py), plus
maintenance_charge_configs.element_id linking each charge head to the
element it was created from. Also registers the "maintenance_elements"
screen in the forms matrix for Society Admin and all Committee roles
(same pattern as f6a7b8c9d0e1_online_payments_form.py).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

revision      = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on    = None

FORM_CODE = "maintenance_elements"
FORM_NAME = "Maintenance Elements"
FORM_DESC = "Master list of maintenance elements charge heads are created from"
_GRANTED_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member",
)

# Both enum types already exist (billing foundation + maintenance_calculation).
charge_type = postgresql.ENUM(name='chargetype', create_type=False)
charge_basis = postgresql.ENUM(name='chargebasis', create_type=False)


def upgrade() -> None:
    op.create_table(
        'maintenance_elements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('society_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bye_law_ref', sa.String(150), nullable=True),
        sa.Column('category', charge_type, nullable=False, server_default='other'),
        sa.Column('default_basis', charge_basis, nullable=False, server_default='fixed'),
        sa.Column('default_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_service_charge', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('gst_applicable', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint('society_id', 'code', name='uq_maintenance_element_code'),
    )
    op.create_index('ix_maintenance_elements_society_id', 'maintenance_elements', ['society_id'])

    op.add_column('maintenance_charge_configs',
                  sa.Column('element_id', postgresql.UUID(as_uuid=True),
                            sa.ForeignKey('maintenance_elements.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_maintenance_charge_configs_element_id', 'maintenance_charge_configs', ['element_id'])

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

    existing = bind.execute(sa.select(forms_table.c.id).where(forms_table.c.code == FORM_CODE)).first()
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
            sa.select(role_forms_table.c.role_id).where(role_forms_table.c.form_id == form_id))
    }
    roles = bind.execute(
        sa.select(roles_table.c.id, roles_table.c.name).where(roles_table.c.name.in_(_GRANTED_ROLES))
    ).fetchall()
    grants = [
        {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id,
         "created_at": now, "updated_at": now, "is_active": True}
        for role_id, _ in roles if role_id not in existing_grants
    ]
    if grants:
        bind.execute(role_forms_table.insert(), grants)


def downgrade() -> None:
    bind = op.get_bind()
    forms_table = sa.table('forms', sa.column('id', UUID(as_uuid=True)), sa.column('code', sa.String))
    row = bind.execute(sa.select(forms_table.c.id).where(forms_table.c.code == FORM_CODE)).first()
    if row:
        role_forms_table = sa.table('role_forms', sa.column('form_id', UUID(as_uuid=True)))
        bind.execute(role_forms_table.delete().where(role_forms_table.c.form_id == row[0]))
        bind.execute(forms_table.delete().where(forms_table.c.id == row[0]))
    op.drop_index('ix_maintenance_charge_configs_element_id', table_name='maintenance_charge_configs')
    op.drop_column('maintenance_charge_configs', 'element_id')
    op.drop_index('ix_maintenance_elements_society_id', table_name='maintenance_elements')
    op.drop_table('maintenance_elements')
