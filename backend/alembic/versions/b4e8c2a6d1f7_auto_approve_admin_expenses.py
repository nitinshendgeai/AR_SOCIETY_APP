"""Let a society post its admin's own expenses without a second approver

Revision ID: b4e8c2a6d1f7
Revises: a3d7e1f9b5c2
Create Date: 2026-10-18

maintenance_settings.auto_approve_admin_expenses: off for every society (a payment voucher still waits for a second
admin / committee member). When a society turns it on, a payment entered by someone who could approve it themselves
is posted as approved at once, so the treasurer's expenses reach the books - and the bills - without a second step.
Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'b4e8c2a6d1f7'
down_revision = 'a3d7e1f9b5c2'
branch_labels = None
depends_on    = None


def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('maintenance_settings')}
    if 'auto_approve_admin_expenses' not in cols:
        op.add_column('maintenance_settings', sa.Column(
            'auto_approve_admin_expenses', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('maintenance_settings', 'auto_approve_admin_expenses')
