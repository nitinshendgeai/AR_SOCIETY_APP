"""Expense ledgers linked to maintenance elements; fines and extra charges per flat

Revision ID: fc2d3e4f5a6b
Revises: fb1c2d3e4f5a
Create Date: 2026-10-03

- accounts.maintenance_element_id: an expense ledger counts towards a maintenance
  element, so what is spent on it is that element's actual cost. The standard
  expense ledgers of societies that already have their books and elements are linked
  to the matching standard element.
- maintenance_charge_configs.auto_from_expenses / expense_months: budget a charge head
  from the linked expenses instead of the typed amount (off by default).
- flat_charges: fines and additional charges on one flat, billed on the next bill.
Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'fc2d3e4f5a6b'
down_revision = 'fb1c2d3e4f5a'
branch_labels = None
depends_on    = None

LINKS = {
    "security_charges": "security", "cctv_maintenance": "security",
    "housekeeping": "housekeeping", "garden": "housekeeping", "pest_control": "housekeeping",
    "lift_maintenance": "lift_maintenance",
    "electricity": "common_electricity", "generator_maintenance": "common_electricity",
    "water_charges": "water_charges", "property_tax": "property_tax",
    "insurance": "insurance", "lease_rent": "lease_rent_na_tax",
}


def _cols(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if 'maintenance_element_id' not in _cols('accounts'):
        op.add_column('accounts', sa.Column('maintenance_element_id', UUID(as_uuid=True),
                                            sa.ForeignKey('maintenance_elements.id', ondelete='SET NULL'), nullable=True))
        op.create_index('ix_accounts_maintenance_element_id', 'accounts', ['maintenance_element_id'])
        for key, code in LINKS.items():
            bind.execute(sa.text("""
                UPDATE accounts a SET maintenance_element_id = e.id
                FROM maintenance_elements e
                WHERE a.system_key = :key AND e.code = :code AND e.society_id = a.society_id
                  AND a.maintenance_element_id IS NULL
            """), {"key": key, "code": code})
    cols = _cols('maintenance_charge_configs')
    if 'auto_from_expenses' not in cols:
        op.add_column('maintenance_charge_configs',
                      sa.Column('auto_from_expenses', sa.Boolean(), nullable=False, server_default=sa.false()))
    if 'expense_months' not in cols:
        op.add_column('maintenance_charge_configs',
                      sa.Column('expense_months', sa.Integer(), nullable=False, server_default='12'))

    if 'flat_charges' not in sa.inspect(bind).get_table_names():
        kind = sa.Enum('fine', 'extra', name='flatchargekind')
        status = sa.Enum('active', 'billed', 'cancelled', name='flatchargestatus')
        op.create_table(
            'flat_charges',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='CASCADE'), nullable=False),
            sa.Column('bill_id', UUID(as_uuid=True), sa.ForeignKey('maintenance_bills.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('cancelled_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('kind', kind, nullable=False, server_default='fine'),
            sa.Column('title', sa.String(150), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('gst_applicable', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('effective_date', sa.Date(), nullable=False),
            sa.Column('recurring', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('status', status, nullable=False, server_default='active'),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
            sa.Column('cancel_reason', sa.Text(), nullable=True),
        )
        for col in ('society_id', 'flat_id', 'bill_id', 'created_by', 'cancelled_by', 'kind', 'effective_date', 'status'):
            op.create_index(f'ix_flat_charges_{col}', 'flat_charges', [col])


def downgrade():
    op.drop_table('flat_charges')
    sa.Enum(name='flatchargekind').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='flatchargestatus').drop(op.get_bind(), checkfirst=True)
    op.drop_column('maintenance_charge_configs', 'expense_months')
    op.drop_column('maintenance_charge_configs', 'auto_from_expenses')
    op.drop_index('ix_accounts_maintenance_element_id', table_name='accounts')
    op.drop_column('accounts', 'maintenance_element_id')
