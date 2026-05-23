"""visitor_gate_management_module

Revision ID: 20247a37e543
Revises: b58680de1da5
Create Date: 2026-05-23

Tables: gates, visitors, visitor_vehicles, visitor_logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '20247a37e543'
down_revision = 'b58680de1da5'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Enums
    gate_type_enum    = sa.Enum('entry','exit','both', name='gatetype')
    visitor_type_enum = sa.Enum('guest','delivery','cab','maintenance','vendor','emergency', name='visitortype')
    visitor_status_enum = sa.Enum('pending','approved','rejected','checked_in','checked_out','expired', name='visitorstatus')

    # ── gates ─────────────────────────────────────────────────────────────────
    op.create_table(
        'gates',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name',       sa.String(100), nullable=False),
        sa.Column('gate_type',  gate_type_enum, nullable=False, server_default='both'),
        sa.Column('location',   sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_gates_id',        'gates', ['id'])
    op.create_index('ix_gates_society_id','gates', ['society_id'])

    # ── visitors ──────────────────────────────────────────────────────────────
    op.create_table(
        'visitors',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('name',             sa.String(255), nullable=False),
        sa.Column('mobile',           sa.String(20), nullable=False),
        sa.Column('visitor_type',     visitor_type_enum, nullable=False, server_default='guest'),
        sa.Column('purpose',          sa.Text(), nullable=True),
        sa.Column('photo_url',        sa.String(500), nullable=True),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',          UUID(as_uuid=True), nullable=True),
        sa.Column('resident_id',      UUID(as_uuid=True), nullable=True),
        sa.Column('gate_id',          UUID(as_uuid=True), nullable=True),
        sa.Column('status',           visitor_status_enum, nullable=False, server_default='pending'),
        sa.Column('expected_arrival', sa.DateTime(), nullable=True),
        sa.Column('checked_in_at',    sa.DateTime(), nullable=True),
        sa.Column('checked_out_at',   sa.DateTime(), nullable=True),
        sa.Column('approved_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at',      sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('logged_by',        UUID(as_uuid=True), nullable=True),
        sa.Column('qr_token',         sa.String(255), nullable=True),
        sa.Column('qr_expires_at',    sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resident_id'], ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['gate_id'],     ['gates.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['logged_by'],   ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_visitors_id',           'visitors', ['id'])
    op.create_index('ix_visitors_mobile',        'visitors', ['mobile'])
    op.create_index('ix_visitors_society_id',    'visitors', ['society_id'])
    op.create_index('ix_visitors_flat_id',       'visitors', ['flat_id'])
    op.create_index('ix_visitors_resident_id',   'visitors', ['resident_id'])
    op.create_index('ix_visitors_status',        'visitors', ['status'])
    op.create_index('ix_visitors_qr_token',      'visitors', ['qr_token'], unique=True)

    # ── visitor_vehicles ──────────────────────────────────────────────────────
    op.create_table(
        'visitor_vehicles',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('visitor_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('vehicle_type',   sa.String(50), nullable=True),
        sa.Column('vehicle_number', sa.String(30), nullable=True),
        sa.Column('vehicle_model',  sa.String(100), nullable=True),
        sa.Column('vehicle_color',  sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['visitor_id'], ['visitors.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_visitor_vehicles_id',             'visitor_vehicles', ['id'])
    op.create_index('ix_visitor_vehicles_visitor_id',     'visitor_vehicles', ['visitor_id'])
    op.create_index('ix_visitor_vehicles_vehicle_number', 'visitor_vehicles', ['vehicle_number'])

    # ── visitor_logs ──────────────────────────────────────────────────────────
    op.create_table(
        'visitor_logs',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('visitor_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('action',       sa.String(50), nullable=False),
        sa.Column('performed_by', UUID(as_uuid=True), nullable=True),
        sa.Column('notes',        sa.Text(), nullable=True),
        sa.Column('gate_id',      UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['visitor_id'],   ['visitors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'], ['users.id'],    ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['gate_id'],      ['gates.id'],    ondelete='SET NULL'),
    )
    op.create_index('ix_visitor_logs_id',         'visitor_logs', ['id'])
    op.create_index('ix_visitor_logs_visitor_id', 'visitor_logs', ['visitor_id'])


def downgrade() -> None:
    op.drop_table('visitor_logs')
    op.drop_table('visitor_vehicles')
    op.drop_table('visitors')
    op.drop_table('gates')
    sa.Enum(name='visitorstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='visitortype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='gatetype').drop(op.get_bind(), checkfirst=True)
