"""charge_head_parking_zone

Revision ID: 2b7c8d9e0f1a
Revises: 1a6b7c8d9e0f
Create Date: 2026-11-01

A charge head may be tied to one parking zone (e.g. Tower Parking AMC): only flats holding a slot in that zone are
billed, per slot held. Also seeds nothing - standard elements are created by the app. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = '2b7c8d9e0f1a'
down_revision = '1a6b7c8d9e0f'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('maintenance_charge_configs')}
    if 'parking_zone_id' not in cols:
        op.add_column('maintenance_charge_configs', sa.Column(
            'parking_zone_id', UUID(as_uuid=True), sa.ForeignKey('parking_zones.id', ondelete='SET NULL'), nullable=True))
        op.create_index('ix_maintenance_charge_configs_parking_zone_id', 'maintenance_charge_configs', ['parking_zone_id'])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('maintenance_charge_configs')}
    if 'parking_zone_id' in cols:
        op.drop_index('ix_maintenance_charge_configs_parking_zone_id', table_name='maintenance_charge_configs')
        op.drop_column('maintenance_charge_configs', 'parking_zone_id')
