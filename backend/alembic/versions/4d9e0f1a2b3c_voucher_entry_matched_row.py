"""Voucher entries cleared together by one bank statement row

Revision ID: 4d9e0f1a2b3c
Revises: 3c8d9e0f1a2b
Create Date: 2026-11-06

voucher_entries.matched_row_id: when several lines of the books are cleared by ONE bank statement row (a deposit slip of
cheques), the row they belong to, so taking the match back releases them all. Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = '4d9e0f1a2b3c'
down_revision = '3c8d9e0f1a2b'
branch_labels = None
depends_on    = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'matched_row_id' not in {c['name'] for c in insp.get_columns('voucher_entries')}:
        op.add_column('voucher_entries', sa.Column('matched_row_id', postgresql.UUID(as_uuid=True), nullable=True))
    if 'ix_voucher_entries_matched_row_id' not in {i['name'] for i in insp.get_indexes('voucher_entries')}:
        op.create_index('ix_voucher_entries_matched_row_id', 'voucher_entries', ['matched_row_id'])


def downgrade():
    op.drop_index('ix_voucher_entries_matched_row_id', table_name='voucher_entries')
    op.drop_column('voucher_entries', 'matched_row_id')
