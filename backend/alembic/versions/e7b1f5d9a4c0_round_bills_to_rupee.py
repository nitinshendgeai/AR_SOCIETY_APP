"""Round bills to the whole rupee

Revision ID: e7b1f5d9a4c0
Revises: d6a0e4c8f3b9
Create Date: 2026-10-24

maintenance_settings.round_to_rupee: the society rounds each bill to the nearest rupee (off by default).
maintenance_bills.round_off: the rounding inside a bill's total (0 on every existing bill). Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'e7b1f5d9a4c0'
down_revision = 'd6a0e4c8f3b9'
branch_labels = None
depends_on    = None


def _add(table, column):
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in cols:
        op.add_column(table, column)


def upgrade():
    _add('maintenance_settings', sa.Column('round_to_rupee', sa.Boolean(), nullable=False, server_default=sa.false()))
    _add('maintenance_bills', sa.Column('round_off', sa.Numeric(12, 2), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('maintenance_bills', 'round_off')
    op.drop_column('maintenance_settings', 'round_to_rupee')
