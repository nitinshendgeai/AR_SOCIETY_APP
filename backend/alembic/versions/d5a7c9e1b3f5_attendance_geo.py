"""Location check for staff attendance: spots, settings and what each check-in reported

Revision ID: d5a7c9e1b3f5
Revises: c3e5a7b9d1f3
Create Date: 2026-11-17

attendance_geo_spots, attendance_geo_settings, attendance_geo_events. Only adds tables; nothing existing is changed. With no
spot set up, attendance behaves exactly as before.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'd5a7c9e1b3f5'
down_revision = 'c3e5a7b9d1f3'
branch_labels = None
depends_on    = None


def _base():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    soc = lambda: sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False)
    if 'attendance_geo_spots' not in existing:
        op.create_table('attendance_geo_spots', *_base(), soc(),
                        sa.Column('name', sa.String(100), nullable=False),
                        sa.Column('latitude', sa.Float(), nullable=False),
                        sa.Column('longitude', sa.Float(), nullable=False),
                        sa.Column('radius_m', sa.Integer(), nullable=False, server_default='10'))
        op.create_index('ix_attendance_geo_spots_society_id', 'attendance_geo_spots', ['society_id'])
    if 'attendance_geo_settings' not in existing:
        op.create_table('attendance_geo_settings', *_base(), soc(),
                        sa.Column('mode', sa.String(10), nullable=False, server_default='flag'),
                        sa.Column('max_accuracy_m', sa.Integer(), nullable=False, server_default='20'),
                        sa.UniqueConstraint('society_id', name='uq_attendance_geo_settings_society'))
        op.create_index('ix_attendance_geo_settings_society_id', 'attendance_geo_settings', ['society_id'])
    if 'attendance_geo_events' not in existing:
        op.create_table('attendance_geo_events', *_base(), soc(),
                        sa.Column('attendance_id', UUID(as_uuid=True), sa.ForeignKey('staff_attendance.id', ondelete='CASCADE'), nullable=False),
                        sa.Column('kind', sa.String(3), nullable=False),
                        sa.Column('status', sa.String(20), nullable=False),
                        sa.Column('latitude', sa.Float(), nullable=True),
                        sa.Column('longitude', sa.Float(), nullable=True),
                        sa.Column('accuracy_m', sa.Float(), nullable=True),
                        sa.Column('distance_m', sa.Float(), nullable=True),
                        sa.Column('spot_name', sa.String(100), nullable=True),
                        sa.Column('mocked', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index('ix_attendance_geo_events_society_id', 'attendance_geo_events', ['society_id'])
        op.create_index('ix_attendance_geo_events_attendance_id', 'attendance_geo_events', ['attendance_id'])


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for t in ('attendance_geo_events', 'attendance_geo_settings', 'attendance_geo_spots'):
        if t in existing:
            op.drop_table(t)
