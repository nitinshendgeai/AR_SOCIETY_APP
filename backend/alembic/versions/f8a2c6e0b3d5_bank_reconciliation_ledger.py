"""Bank reconciliation against the books

Revision ID: f8a2c6e0b3d5
Revises: e7b1f5d9a4c0
Create Date: 2026-10-25

voucher_entries.cleared_date / cleared_by: the day the bank cleared a line of a bank ledger (empty: not cleared yet),
which is what the Bank Reconciliation Statement is built from.
vendor_payment_transactions.bank_account_id / online_payment_submissions.deposit_account_id: the cash or bank ledger a
vendor payment was made from and a resident's payment was deposited into (empty: cash in hand, or the default bank).
bank_statement_entries.direction / bank_account_id / matched_entry_id: a statement row can now be a debit as well as a
credit, belongs to one of the society's bank ledgers and can be matched to the books' own line (not only to a resident's
online payment). Additive and idempotent: every existing row is a credit with nothing cleared.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'f8a2c6e0b3d5'
down_revision = 'e7b1f5d9a4c0'
branch_labels = None
depends_on    = None


def _has(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table, name):
    return name in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    if not _has('voucher_entries', 'cleared_date'):
        op.add_column('voucher_entries', sa.Column('cleared_date', sa.Date(), nullable=True))
    if not _has('voucher_entries', 'cleared_by'):
        op.add_column('voucher_entries', sa.Column('cleared_by', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_voucher_entries_cleared_by', 'voucher_entries', 'users', ['cleared_by'], ['id'],
                              ondelete='SET NULL')
    if not _has_index('voucher_entries', 'ix_voucher_entries_cleared_date'):
        op.create_index('ix_voucher_entries_cleared_date', 'voucher_entries', ['cleared_date'])

    if not _has('vendor_payment_transactions', 'bank_account_id'):
        op.add_column('vendor_payment_transactions',
                      sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_vendor_payment_transactions_bank_account', 'vendor_payment_transactions',
                              'accounts', ['bank_account_id'], ['id'], ondelete='SET NULL')

    if not _has('online_payment_submissions', 'deposit_account_id'):
        op.add_column('online_payment_submissions',
                      sa.Column('deposit_account_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_online_payment_submissions_deposit_account', 'online_payment_submissions',
                              'accounts', ['deposit_account_id'], ['id'], ondelete='SET NULL')

    if not _has('bank_statement_entries', 'direction'):
        op.add_column('bank_statement_entries',
                      sa.Column('direction', sa.String(length=6), nullable=False, server_default='credit'))
    if not _has('bank_statement_entries', 'bank_account_id'):
        op.add_column('bank_statement_entries',
                      sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_bank_statement_entries_bank_account', 'bank_statement_entries', 'accounts',
                              ['bank_account_id'], ['id'], ondelete='SET NULL')
    if not _has_index('bank_statement_entries', 'ix_bank_statement_entries_bank_account_id'):
        op.create_index('ix_bank_statement_entries_bank_account_id', 'bank_statement_entries', ['bank_account_id'])
    if not _has('bank_statement_entries', 'matched_entry_id'):
        op.add_column('bank_statement_entries',
                      sa.Column('matched_entry_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_bank_statement_entries_matched_entry', 'bank_statement_entries', 'voucher_entries',
                              ['matched_entry_id'], ['id'], ondelete='SET NULL')
    if not _has_index('bank_statement_entries', 'ix_bank_statement_entries_matched_entry_id'):
        op.create_index('ix_bank_statement_entries_matched_entry_id', 'bank_statement_entries', ['matched_entry_id'])


def downgrade():
    op.drop_constraint('fk_online_payment_submissions_deposit_account', 'online_payment_submissions',
                       type_='foreignkey')
    op.drop_column('online_payment_submissions', 'deposit_account_id')
    op.drop_constraint('fk_vendor_payment_transactions_bank_account', 'vendor_payment_transactions',
                       type_='foreignkey')
    op.drop_column('vendor_payment_transactions', 'bank_account_id')
    op.drop_index('ix_bank_statement_entries_matched_entry_id', table_name='bank_statement_entries')
    op.drop_constraint('fk_bank_statement_entries_matched_entry', 'bank_statement_entries', type_='foreignkey')
    op.drop_column('bank_statement_entries', 'matched_entry_id')
    op.drop_index('ix_bank_statement_entries_bank_account_id', table_name='bank_statement_entries')
    op.drop_constraint('fk_bank_statement_entries_bank_account', 'bank_statement_entries', type_='foreignkey')
    op.drop_column('bank_statement_entries', 'bank_account_id')
    op.drop_column('bank_statement_entries', 'direction')
    op.drop_index('ix_voucher_entries_cleared_date', table_name='voucher_entries')
    op.drop_constraint('fk_voucher_entries_cleared_by', 'voucher_entries', type_='foreignkey')
    op.drop_column('voucher_entries', 'cleared_by')
    op.drop_column('voucher_entries', 'cleared_date')
