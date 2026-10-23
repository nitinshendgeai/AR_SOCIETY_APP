"""Vendor type for TDS, and TDS deducted when a vendor is paid

Revision ID: c5f9d3b7e2a8
Revises: b4e8c2a6d1f7
Create Date: 2026-10-23

vendors: constitution (individual, HUF, firm, company...), the usual TDS section and a lower-deduction certificate.
accounting_tax_configurations: who the rule is for (payee_class) and the single-payment limit.
vendor_payment_transactions: the TDS taken off each payment. Additive and idempotent; existing payments keep 0 TDS
(a bill that already carries TDS from when it was booked is unchanged).
"""
import sqlalchemy as sa
from alembic import op

revision      = 'c5f9d3b7e2a8'
down_revision = 'b4e8c2a6d1f7'
branch_labels = None
depends_on    = None


def _add(table, column):
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in cols:
        op.add_column(table, column)


def upgrade():
    _add('vendors', sa.Column('constitution', sa.String(30), nullable=True))
    _add('vendors', sa.Column('tds_section', sa.String(30), nullable=True))
    _add('vendors', sa.Column('tds_lower_rate', sa.Numeric(7, 4), nullable=True))
    _add('vendors', sa.Column('tds_lower_cert_no', sa.String(50), nullable=True))
    _add('vendors', sa.Column('tds_lower_valid_from', sa.Date(), nullable=True))
    _add('vendors', sa.Column('tds_lower_valid_to', sa.Date(), nullable=True))

    _add('accounting_tax_configurations', sa.Column(
        'payee_class', sa.String(20), nullable=False, server_default='any'))
    _add('accounting_tax_configurations', sa.Column('single_threshold', sa.Numeric(14, 2), nullable=True))

    zero = sa.text('0')
    _add('vendor_payment_transactions', sa.Column('taxable_value', sa.Numeric(12, 2), nullable=False, server_default=zero))
    _add('vendor_payment_transactions', sa.Column('tds_section', sa.String(30), nullable=True))
    _add('vendor_payment_transactions', sa.Column('tds_rate', sa.Numeric(7, 4), nullable=False, server_default=zero))
    _add('vendor_payment_transactions', sa.Column('tds_base_amount', sa.Numeric(12, 2), nullable=False, server_default=zero))
    _add('vendor_payment_transactions', sa.Column('tds_amount', sa.Numeric(12, 2), nullable=False, server_default=zero))
    _add('vendor_payment_transactions', sa.Column('tds_note', sa.String(255), nullable=True))


def downgrade():
    for c in ('tds_note', 'tds_amount', 'tds_base_amount', 'tds_rate', 'tds_section', 'taxable_value'):
        op.drop_column('vendor_payment_transactions', c)
    op.drop_column('accounting_tax_configurations', 'single_threshold')
    op.drop_column('accounting_tax_configurations', 'payee_class')
    for c in ('tds_lower_valid_to', 'tds_lower_valid_from', 'tds_lower_cert_no', 'tds_lower_rate', 'tds_section',
              'constitution'):
        op.drop_column('vendors', c)
