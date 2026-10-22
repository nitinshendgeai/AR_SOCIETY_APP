"""Share a cycle's actual expenses out exactly, and keep the working

Revision ID: a3d7e1f9b5c2
Revises: f2c5d9e7a1b3
Create Date: 2026-10-17

A charge head that bills "from expenses" could only read the books as a trailing, annualised average. This adds the
period mode: the approved expenses dated inside the billing cycle's own period are shared out exactly, and the
working is kept.

- maintenance_charge_configs.expense_mode  'trailing' (every existing head, the original behaviour) or 'period'
- billing_expense_allocations              one row per (cycle, charge head): the pool, the method, the weights, the
                                           rate - written when the bills are generated and not changed afterwards
- billing_expense_sources                  the vouchers that made up each pool
- invoice_line_items.allocation_id         the bill line -> its allocation (empty on every other line)

Everything is additive; existing rows and bills are untouched and keep working as before. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'a3d7e1f9b5c2'
down_revision = 'f2c5d9e7a1b3'
branch_labels = None
depends_on    = None


def _columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if 'expense_mode' not in _columns('maintenance_charge_configs'):
        op.add_column('maintenance_charge_configs',
                      sa.Column('expense_mode', sa.String(10), nullable=False, server_default='trailing'))

    if 'billing_expense_allocations' not in tables:
        op.create_table(
            'billing_expense_allocations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('cycle_id', UUID(as_uuid=True), sa.ForeignKey('billing_cycles.id', ondelete='CASCADE'), nullable=False),
            sa.Column('charge_id', UUID(as_uuid=True), sa.ForeignKey('maintenance_charge_configs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('element_id', UUID(as_uuid=True), sa.ForeignKey('maintenance_elements.id', ondelete='SET NULL'), nullable=True),
            sa.Column('charge_name', sa.String(150), nullable=False),
            sa.Column('element_name', sa.String(150), nullable=True),
            sa.Column('method', sa.String(10), nullable=False),
            sa.Column('period_start', sa.Date(), nullable=False),
            sa.Column('period_end', sa.Date(), nullable=False),
            sa.Column('pool_amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('allocated_amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('eligible_flats', sa.Integer(), nullable=False),
            sa.Column('total_weight', sa.Numeric(18, 4), nullable=False),
            sa.Column('rate', sa.Numeric(18, 8), nullable=False),
        )
        for col in ('society_id', 'cycle_id', 'charge_id', 'element_id'):
            op.create_index(f'ix_billing_expense_allocations_{col}', 'billing_expense_allocations', [col])

    if 'billing_expense_sources' not in tables:
        op.create_table(
            'billing_expense_sources',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('allocation_id', UUID(as_uuid=True),
                      sa.ForeignKey('billing_expense_allocations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='SET NULL'), nullable=True),
            sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('voucher_number', sa.String(40), nullable=False),
            sa.Column('voucher_date', sa.Date(), nullable=False),
            sa.Column('ledger_name', sa.String(150), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        )
        op.create_index('ix_billing_expense_sources_allocation_id', 'billing_expense_sources', ['allocation_id'])
        op.create_index('ix_billing_expense_sources_voucher_id', 'billing_expense_sources', ['voucher_id'])

    if 'allocation_id' not in _columns('invoice_line_items'):
        op.add_column('invoice_line_items', sa.Column(
            'allocation_id', UUID(as_uuid=True),
            sa.ForeignKey('billing_expense_allocations.id', ondelete='SET NULL'), nullable=True))
        op.create_index('ix_invoice_line_items_allocation_id', 'invoice_line_items', ['allocation_id'])


def downgrade():
    op.drop_index('ix_invoice_line_items_allocation_id', table_name='invoice_line_items')
    op.drop_column('invoice_line_items', 'allocation_id')
    op.drop_table('billing_expense_sources')
    op.drop_table('billing_expense_allocations')
    op.drop_column('maintenance_charge_configs', 'expense_mode')
