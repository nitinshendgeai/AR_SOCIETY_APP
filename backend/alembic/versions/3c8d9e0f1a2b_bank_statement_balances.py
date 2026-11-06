"""Bank statement balances

Revision ID: 3c8d9e0f1a2b
Revises: 2b7c8d9e0f1a
Create Date: 2026-11-06

bank_statement_balances: the balance the bank's own statement shows for a bank ledger on a day (read from an imported PDF,
or typed in), so the Bank Reconciliation Statement can be checked against it. Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = '3c8d9e0f1a2b'
down_revision = '2b7c8d9e0f1a'
branch_labels = None
depends_on    = None


def upgrade():
    if 'bank_statement_balances' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'bank_statement_balances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('society_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('as_on', sa.Date(), nullable=False),
        sa.Column('balance', sa.Numeric(14, 2), nullable=False),
        sa.Column('source', sa.String(10), nullable=False, server_default='manual'),
        sa.Column('entered_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.UniqueConstraint('bank_account_id', 'as_on', name='uq_bank_statement_balance_day'),
    )
    op.create_index('ix_bank_statement_balances_society_id', 'bank_statement_balances', ['society_id'])
    op.create_index('ix_bank_statement_balances_bank_account_id', 'bank_statement_balances', ['bank_account_id'])


def downgrade():
    op.drop_table('bank_statement_balances')
