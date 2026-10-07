"""Recurring monthly expenses

Revision ID: 1b8c9d0e1f2a
Revises: 0a7b8c9d0e1f
Create Date: 2026-10-07

Standing monthly expenses (security agency, lift AMC, rent) that come up as due each month for a person to
confirm, and the record of what became of each month. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = '1b8c9d0e1f2a'
down_revision = '0a7b8c9d0e1f'
branch_labels = None
depends_on    = None


def _base_columns():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if 'recurring_expenses' not in tables:
        op.create_table(
            'recurring_expenses',
            *_base_columns(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(150), nullable=False),
            sa.Column('expense_account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('paid_from_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('amount', sa.Numeric(14, 2), nullable=True),
            sa.Column('day_of_month', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('start_month', sa.Date(), nullable=False),
            sa.Column('end_month', sa.Date(), nullable=True),
            sa.Column('payee', sa.String(255), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_recurring_expenses_society_id', 'recurring_expenses', ['society_id'])
        op.create_index('ix_recurring_expenses_expense_account_id', 'recurring_expenses', ['expense_account_id'])
    if 'recurring_expense_runs' not in tables:
        op.create_table(
            'recurring_expense_runs',
            *_base_columns(),
            sa.Column('recurring_id', UUID(as_uuid=True), sa.ForeignKey('recurring_expenses.id', ondelete='CASCADE'), nullable=False),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('month', sa.Date(), nullable=False),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='SET NULL'), nullable=True),
            sa.Column('skipped', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('skip_reason', sa.Text(), nullable=True),
            sa.Column('decided_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.UniqueConstraint('recurring_id', 'month', name='uq_recurring_run_month'),
        )
        op.create_index('ix_recurring_expense_runs_recurring_id', 'recurring_expense_runs', ['recurring_id'])
        op.create_index('ix_recurring_expense_runs_society_id', 'recurring_expense_runs', ['society_id'])


def downgrade():
    op.drop_table('recurring_expense_runs')
    op.drop_table('recurring_expenses')
