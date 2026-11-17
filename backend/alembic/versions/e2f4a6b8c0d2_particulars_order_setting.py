"""How the Boxed bill orders its particulars: a per-society setting

Revision ID: e2f4a6b8c0d2
Revises: c9e1a3b5d7f9
Create Date: 2026-11-18

maintenance_settings.particulars_order: "elements" (the order the society arranged its elements in; what every society
has) or "amount" (the largest amount first). Additive and idempotent: every existing society keeps the element order.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'e2f4a6b8c0d2'
down_revision = 'c9e1a3b5d7f9'
branch_labels = None
depends_on    = None


def _has(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has('maintenance_settings', 'particulars_order'):
        op.add_column('maintenance_settings',
                      sa.Column('particulars_order', sa.String(length=20), nullable=False, server_default='elements'))


def downgrade():
    if _has('maintenance_settings', 'particulars_order'):
        op.drop_column('maintenance_settings', 'particulars_order')
