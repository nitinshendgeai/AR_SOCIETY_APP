"""parking_zone_rate

Revision ID: 1a6b7c8d9e0f
Revises: 0f5a6b7c8d9e
Create Date: 2026-10-31

A parking zone (Tower, Stack...) may carry a monthly rate for one four-wheeler slot. Billing uses it for an active
allocation that has no charge of its own; nothing changes for zones without a rate. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = '1a6b7c8d9e0f'
down_revision = '0f5a6b7c8d9e'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('parking_zones')}
    if 'monthly_rate' not in cols:
        op.add_column('parking_zones', sa.Column('monthly_rate', sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('parking_zones')}
    if 'monthly_rate' in cols:
        op.drop_column('parking_zones', 'monthly_rate')
