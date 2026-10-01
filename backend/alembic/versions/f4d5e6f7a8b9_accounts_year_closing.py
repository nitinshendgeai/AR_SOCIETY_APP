"""Accounts: year-end closing and reversals

Revision ID: f4d5e6f7a8b9
Revises: f3c4d5e6f7a8
Create Date: 2026-10-01

Adds account_year_closings (a financial year whose books are closed, with
its result and Reserve Fund transfer) and, on vouchers, reversal_of_id /
reversed_at: a posting of a closed year whose bill or payment is cancelled
later is reversed in the open year instead. Also puts the opening-balance
side of liability and income ledgers with no opening balance yet on Cr
(they were created as Dr). Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'f4d5e6f7a8b9'
down_revision = 'f3c4d5e6f7a8'
branch_labels = None
depends_on    = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('vouchers')}
    if 'reversal_of_id' not in columns:
        op.add_column('vouchers', sa.Column('reversal_of_id', UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_vouchers_reversal_of', 'vouchers', 'vouchers',
                              ['reversal_of_id'], ['id'], ondelete='SET NULL')
    if 'reversed_at' not in columns:
        op.add_column('vouchers', sa.Column('reversed_at', sa.DateTime(), nullable=True))

    if 'account_year_closings' not in inspector.get_table_names():
        op.create_table(
            'account_year_closings',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('fiscal_year', sa.String(7), nullable=False),
            sa.Column('year_start', sa.Date(), nullable=False),
            sa.Column('year_end', sa.Date(), nullable=False),
            sa.Column('total_income', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('total_expenditure', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('surplus', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('reserve_pct', sa.Numeric(5, 2), nullable=False, server_default='0'),
            sa.Column('reserve_transfer', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('closing_voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='SET NULL'), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('closed_at', sa.DateTime(), nullable=False),
            sa.Column('closed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reopened_at', sa.DateTime(), nullable=True),
            sa.Column('reopened_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reopen_reason', sa.Text(), nullable=True),
        )
        op.create_index('ix_account_year_closings_society_id', 'account_year_closings', ['society_id'])
        op.create_index('ix_account_year_closings_fiscal_year', 'account_year_closings', ['fiscal_year'])

    op.execute("""
        UPDATE accounts SET opening_type = 'cr'
        WHERE opening_balance = 0 AND opening_type = 'dr'
          AND group_id IN (SELECT id FROM account_groups WHERE nature IN ('liability', 'income'))
    """)


def downgrade():
    op.drop_table('account_year_closings')
    op.drop_constraint('fk_vouchers_reversal_of', 'vouchers', type_='foreignkey')
    op.drop_column('vouchers', 'reversed_at')
    op.drop_column('vouchers', 'reversal_of_id')
