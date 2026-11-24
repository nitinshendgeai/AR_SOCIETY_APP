"""Round bills up to the next 50

Revision ID: c3e5a7b9d1f2
Revises: a7c9e1b3d5f7
Create Date: 2026-11-24

maintenance_settings.round_up_step: 0 (the default) leaves bills as they are; 50 rounds each bill up to the next multiple of
50 (a bill that is already a multiple of 50 is unchanged). Additive, idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'c3e5a7b9d1f2'
down_revision = 'a7c9e1b3d5f7'
branch_labels = None
depends_on    = None


def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('maintenance_settings')}
    if 'round_up_step' not in cols:
        op.add_column('maintenance_settings',
                      sa.Column('round_up_step', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('maintenance_settings')}
    if 'round_up_step' in cols:
        op.drop_column('maintenance_settings', 'round_up_step')
