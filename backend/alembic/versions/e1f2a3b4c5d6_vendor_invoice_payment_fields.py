"""vendor_invoices payment_mode + bank_name

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-23

Adds payment_mode (how the vendor was paid) and bank_name to
vendor_invoices, so recording a vendor payment can capture the same
detail the resident-facing payment flow already does. Purely additive;
existing rows get NULL for both (no prior payment mode was ever
recorded).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on    = None

vendor_payment_mode = postgresql.ENUM(
    'cash', 'upi', 'bank_transfer', 'cheque', 'neft', 'rtgs',
    name='vendorpaymentmode',
)


def upgrade() -> None:
    vendor_payment_mode.create(op.get_bind(), checkfirst=True)
    op.add_column('vendor_invoices', sa.Column('payment_mode', vendor_payment_mode, nullable=True))
    op.add_column('vendor_invoices', sa.Column('bank_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('vendor_invoices', 'bank_name')
    op.drop_column('vendor_invoices', 'payment_mode')
    vendor_payment_mode.drop(op.get_bind(), checkfirst=True)
