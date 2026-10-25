"""The society chooses how its maintenance bill prints

Revision ID: d6f8a0c2e4b6
Revises: c5f7b9d1e3a5
Create Date: 2026-10-25

maintenance_settings.bill_layout: "standard" (the heads grouped into the fixed list; what every society had) or "classic"
(every head on its own line, numbered notes, and the previous bill's receipt slip at the foot). Additive and idempotent:
every existing society keeps the standard layout.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'd6f8a0c2e4b6'
down_revision = 'c5f7b9d1e3a5'
branch_labels = None
depends_on    = None


def _has(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has('maintenance_settings', 'bill_layout'):
        op.add_column('maintenance_settings',
                      sa.Column('bill_layout', sa.String(length=20), nullable=False, server_default='standard'))


def downgrade():
    if _has('maintenance_settings', 'bill_layout'):
        op.drop_column('maintenance_settings', 'bill_layout')
