"""Petty cash: float settings and cash counts

Revision ID: 8b3c4d5e6f7a
Revises: 7a2b3c4d5e6f
Create Date: 2026-11-07

petty_cash_settings: one row per society (the float to top up to, the limit for one petty expense, who holds the cash).
petty_cash_counts: the cash counted in the box on a day against what the books said. Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = '8b3c4d5e6f7a'
down_revision = '7a2b3c4d5e6f'
branch_labels = None
depends_on    = None


def _base_columns(uuid):
    return [
        sa.Column('id', uuid, primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', uuid, sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
    ]


def upgrade():
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()
    uuid = postgresql.UUID(as_uuid=True)
    if 'petty_cash_settings' not in tables:
        op.create_table(
            'petty_cash_settings', *_base_columns(uuid),
            sa.Column('float_amount', sa.Numeric(12, 2), nullable=True),
            sa.Column('expense_limit', sa.Numeric(12, 2), nullable=True),
            sa.Column('custodian_name', sa.String(150), nullable=True),
            sa.UniqueConstraint('society_id', name='uq_petty_cash_settings_society'),
        )
        op.create_index('ix_petty_cash_settings_society_id', 'petty_cash_settings', ['society_id'])
    if 'petty_cash_counts' not in tables:
        op.create_table(
            'petty_cash_counts', *_base_columns(uuid),
            sa.Column('count_date', sa.Date(), nullable=False),
            sa.Column('counted_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('book_balance', sa.Numeric(12, 2), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('counted_by', uuid, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_petty_cash_counts_society_id', 'petty_cash_counts', ['society_id'])
        op.create_index('ix_petty_cash_counts_count_date', 'petty_cash_counts', ['count_date'])


def downgrade():
    op.drop_table('petty_cash_counts')
    op.drop_table('petty_cash_settings')
