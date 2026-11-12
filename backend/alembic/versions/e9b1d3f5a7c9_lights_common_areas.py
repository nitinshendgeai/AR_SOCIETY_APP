"""Lights check: common areas (parking, lobby, gym, podium, refuse area)

Revision ID: e9b1d3f5a7c9
Revises: d7a9c1e3f5b7
Create Date: 2026-11-12

common_areas: a place the Manager or Admin names (optionally tied to a wing). common_area_items: how many tube lights, spot
lights, drum lights, halogens or cameras it holds. light_points gains area_id, and its wing and floor become optional,
because a light in a common area belongs to the area, not to a floor. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'e9b1d3f5a7c9'
down_revision = 'd7a9c1e3f5b7'
branch_labels = None
depends_on    = None


def _mixin():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if 'common_areas' not in tables:
        op.create_table(
            'common_areas', *_mixin(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('wing_id', UUID(as_uuid=True), sa.ForeignKey('wings.id', ondelete='SET NULL'), nullable=True),
            sa.Column('name', sa.String(80), nullable=False),
        )
        op.create_index('ix_common_areas_society_id', 'common_areas', ['society_id'])
    if 'common_area_items' not in tables:
        op.create_table(
            'common_area_items', *_mixin(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('area_id', UUID(as_uuid=True), sa.ForeignKey('common_areas.id', ondelete='CASCADE'), nullable=False),
            sa.Column('kind', sa.String(10), nullable=False),
            sa.Column('count', sa.Integer(), nullable=False),
        )
        op.create_index('ix_common_area_items_society_id', 'common_area_items', ['society_id'])
        op.create_index('ix_common_area_items_area_id', 'common_area_items', ['area_id'])

    cols = {c['name'] for c in sa.inspect(bind).get_columns('light_points')}
    if 'area_id' not in cols:
        op.add_column('light_points', sa.Column('area_id', UUID(as_uuid=True),
                                                sa.ForeignKey('common_areas.id', ondelete='CASCADE'), nullable=True))
        op.create_index('ix_light_points_area_id', 'light_points', ['area_id'])
    op.alter_column('light_points', 'wing_id', existing_type=UUID(as_uuid=True), nullable=True)
    op.alter_column('light_points', 'floor_number', existing_type=sa.Integer(), nullable=True)


def downgrade():
    bind = op.get_bind()
    # Lights of common areas have no wing or floor, so they cannot stay once those are required again.
    op.execute("DELETE FROM light_check_entries WHERE point_id IN (SELECT id FROM light_points WHERE area_id IS NOT NULL)")
    op.execute("DELETE FROM light_points WHERE area_id IS NOT NULL")
    op.alter_column('light_points', 'floor_number', existing_type=sa.Integer(), nullable=False)
    op.alter_column('light_points', 'wing_id', existing_type=UUID(as_uuid=True), nullable=False)
    cols = {c['name'] for c in sa.inspect(bind).get_columns('light_points')}
    if 'area_id' in cols:
        op.drop_index('ix_light_points_area_id', table_name='light_points')
        op.drop_column('light_points', 'area_id')
    tables = set(sa.inspect(bind).get_table_names())
    if 'common_area_items' in tables:
        op.drop_table('common_area_items')
    if 'common_areas' in tables:
        op.drop_table('common_areas')
