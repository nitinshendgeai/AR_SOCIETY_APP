"""parking_and_notice_modules

Revision ID: c79ac126b2c8
Revises: 31b688f5de60
Create Date: 2026-05-26

Parking (7 tables): parking_zones, parking_floors, parking_slots,
  parking_allocations, visitor_parking, parking_violations, parking_access_logs

Notice (5 tables): notices, notice_acknowledgements, announcements,
  communication_logs, emergency_alerts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision      = 'c79ac126b2c8'
down_revision = '31b688f5de60'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── PARKING ENUMS ─────────────────────────────────────────────────────────
    slot_type_e    = sa.Enum('resident','tenant','visitor','staff','reserved','disabled', name='slottype')
    slot_status_e  = sa.Enum('available','occupied','reserved','blocked','under_maintenance', name='slotstatus')
    alloc_status_e = sa.Enum('active','released','expired','suspended', name='allocationstatus')
    vp_status_e    = sa.Enum('active','completed','expired','cancelled', name='visitorparkingstatus')
    violation_e    = sa.Enum('unauthorized','expired_permit','wrong_slot','double_parking',
                             'blocked_access','restricted_zone','no_parking', name='violationtype')
    access_type_e  = sa.Enum('entry','exit', name='accesstype')
    access_method_e= sa.Enum('manual','rfid','anpr','app','biometric', name='accessmethod')

    # ── parking_zones ─────────────────────────────────────────────────────────
    op.create_table('parking_zones',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('name',        sa.String(100), nullable=False),
        sa.Column('code',        sa.String(20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('total_slots', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_parking_zones_id',        'parking_zones', ['id'])
    op.create_index('ix_parking_zones_society_id','parking_zones', ['society_id'])

    # ── parking_floors ────────────────────────────────────────────────────────
    op.create_table('parking_floors',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('zone_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('name',        sa.String(50), nullable=False),
        sa.Column('level',       sa.Integer(), nullable=True),
        sa.Column('total_slots', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['zone_id'],    ['parking_zones.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],     ondelete='CASCADE'),
    )
    op.create_index('ix_parking_floors_id',      'parking_floors', ['id'])
    op.create_index('ix_parking_floors_zone_id', 'parking_floors', ['zone_id'])

    # ── parking_slots ─────────────────────────────────────────────────────────
    op.create_table('parking_slots',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('zone_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('floor_id',         UUID(as_uuid=True), nullable=True),
        sa.Column('slot_number',      sa.String(20), nullable=False),
        sa.Column('slot_type',        slot_type_e, nullable=False, server_default='resident'),
        sa.Column('status',           slot_status_e, nullable=False, server_default='available'),
        sa.Column('length_ft',        sa.Integer(), nullable=True),
        sa.Column('width_ft',         sa.Integer(), nullable=True),
        sa.Column('is_covered',       sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_ev_charging',   sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rfid_reader_id',   sa.String(100), nullable=True),
        sa.Column('camera_id',        sa.String(100), nullable=True),
        sa.Column('barrier_id',       sa.String(100), nullable=True),
        sa.Column('notes',            sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['zone_id'],    ['parking_zones.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['floor_id'],   ['parking_floors.id'],ondelete='SET NULL'),
    )
    op.create_index('ix_parking_slots_id',          'parking_slots', ['id'])
    op.create_index('ix_parking_slots_society_id',  'parking_slots', ['society_id'])
    op.create_index('ix_parking_slots_zone_id',     'parking_slots', ['zone_id'])
    op.create_index('ix_parking_slots_slot_number', 'parking_slots', ['slot_number'])
    op.create_index('ix_parking_slots_slot_type',   'parking_slots', ['slot_type'])
    op.create_index('ix_parking_slots_status',      'parking_slots', ['status'])

    # ── parking_allocations ───────────────────────────────────────────────────
    op.create_table('parking_allocations',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',        sa.DateTime(), nullable=False),
        sa.Column('updated_at',        sa.DateTime(), nullable=False),
        sa.Column('is_active',         sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',        UUID(as_uuid=True), nullable=False),
        sa.Column('slot_id',           UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',           UUID(as_uuid=True), nullable=True),
        sa.Column('vehicle_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('allocated_to_user', UUID(as_uuid=True), nullable=True),
        sa.Column('allocated_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('allocation_type',   slot_type_e, nullable=False),
        sa.Column('status',            alloc_status_e, nullable=False, server_default='active'),
        sa.Column('start_date',        sa.Date(), nullable=False),
        sa.Column('end_date',          sa.Date(), nullable=True),
        sa.Column('monthly_charge',    sa.Integer(), nullable=True),
        sa.Column('notes',             sa.Text(), nullable=True),
        sa.Column('released_at',       sa.DateTime(), nullable=True),
        sa.Column('released_by',       UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],        ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'],           ['parking_slots.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],           ['flats.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vehicle_id'],        ['vehicles.id'],       ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['allocated_to_user'], ['users.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['allocated_by'],      ['users.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['released_by'],       ['users.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_parking_allocations_id',       'parking_allocations', ['id'])
    op.create_index('ix_parking_allocations_slot_id',  'parking_allocations', ['slot_id'])
    op.create_index('ix_parking_allocations_flat_id',  'parking_allocations', ['flat_id'])
    op.create_index('ix_parking_allocations_status',   'parking_allocations', ['status'])

    # ── visitor_parking ───────────────────────────────────────────────────────
    op.create_table('visitor_parking',
        sa.Column('id',                     UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',             sa.DateTime(), nullable=False),
        sa.Column('updated_at',             sa.DateTime(), nullable=False),
        sa.Column('is_active',              sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',             UUID(as_uuid=True), nullable=False),
        sa.Column('slot_id',                UUID(as_uuid=True), nullable=True),
        sa.Column('visitor_id',             UUID(as_uuid=True), nullable=True),
        sa.Column('vehicle_number',         sa.String(30), nullable=False),
        sa.Column('vehicle_type',           sa.String(50), nullable=True),
        sa.Column('assigned_by',            UUID(as_uuid=True), nullable=True),
        sa.Column('check_in_time',          sa.DateTime(), nullable=True),
        sa.Column('check_out_time',         sa.DateTime(), nullable=True),
        sa.Column('expected_duration_hours',sa.Integer(), nullable=False, server_default='4'),
        sa.Column('status',                 vp_status_e, nullable=False, server_default='active'),
        sa.Column('purpose',                sa.String(255), nullable=True),
        sa.Column('host_flat_id',           UUID(as_uuid=True), nullable=True),
        sa.Column('notes',                  sa.Text(), nullable=True),
        sa.Column('temp_access_code',       sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'],     ['parking_slots.id'],  ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['host_flat_id'],['flats.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_visitor_parking_id',             'visitor_parking', ['id'])
    op.create_index('ix_visitor_parking_society_id',     'visitor_parking', ['society_id'])
    op.create_index('ix_visitor_parking_vehicle_number', 'visitor_parking', ['vehicle_number'])
    op.create_index('ix_visitor_parking_status',         'visitor_parking', ['status'])

    # ── parking_violations ────────────────────────────────────────────────────
    op.create_table('parking_violations',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('slot_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('vehicle_number', sa.String(30), nullable=False),
        sa.Column('vehicle_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('violation_type', violation_e, nullable=False),
        sa.Column('reported_by',    UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_by',    UUID(as_uuid=True), nullable=True),
        sa.Column('description',    sa.Text(), nullable=True),
        sa.Column('photo_url',      sa.String(500), nullable=True),
        sa.Column('is_resolved',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at',    sa.DateTime(), nullable=True),
        sa.Column('fine_amount',    sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'],     ['parking_slots.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vehicle_id'],  ['vehicles.id'],      ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reported_by'], ['users.id'],         ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'],         ondelete='SET NULL'),
    )
    op.create_index('ix_parking_violations_id',             'parking_violations', ['id'])
    op.create_index('ix_parking_violations_society_id',     'parking_violations', ['society_id'])
    op.create_index('ix_parking_violations_vehicle_number', 'parking_violations', ['vehicle_number'])
    op.create_index('ix_parking_violations_is_resolved',    'parking_violations', ['is_resolved'])

    # ── parking_access_logs ───────────────────────────────────────────────────
    op.create_table('parking_access_logs',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('slot_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('vehicle_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('vehicle_number', sa.String(30), nullable=False),
        sa.Column('user_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('access_type',    access_type_e, nullable=False),
        sa.Column('access_method',  access_method_e, nullable=False, server_default='manual'),
        sa.Column('access_time',    sa.DateTime(), nullable=False),
        sa.Column('gate_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('rfid_tag',       sa.String(100), nullable=True),
        sa.Column('is_authorized',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes',          sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'],    ['parking_slots.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'],      ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'],    ['users.id'],         ondelete='SET NULL'),
    )
    op.create_index('ix_parking_access_logs_id',             'parking_access_logs', ['id'])
    op.create_index('ix_parking_access_logs_society_id',     'parking_access_logs', ['society_id'])
    op.create_index('ix_parking_access_logs_vehicle_number', 'parking_access_logs', ['vehicle_number'])
    op.create_index('ix_parking_access_logs_access_time',    'parking_access_logs', ['access_time'])
    op.create_index('ix_parking_access_logs_is_authorized',  'parking_access_logs', ['is_authorized'])

    # ── NOTICE ENUMS ──────────────────────────────────────────────────────────
    notice_cat_e  = sa.Enum('general','emergency','maintenance','events','security','parking',
                            'water_shutdown','power_shutdown','staff_notice','finance','amenities',
                            name='noticecategory')
    notice_pri_e  = sa.Enum('low','normal','high','urgent', name='noticepriority')
    notice_st_e   = sa.Enum('draft','published','expired','archived', name='noticestatus')
    audience_e    = sa.Enum('all_residents','owners_only','tenants_only','specific_wings',
                            'specific_flats','all_staff','security_team','committee','all',
                            name='audiencetype')
    alert_type_e  = sa.Enum('fire','water_leakage','lift_failure','power_failure','security_threat',
                            'medical','earthquake','flood','gas_leak','other', name='alerttype')
    alert_st_e    = sa.Enum('active','resolved','cancelled', name='alertstatus')

    # ── notices ───────────────────────────────────────────────────────────────
    op.create_table('notices',
        sa.Column('id',                      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',              sa.DateTime(), nullable=False),
        sa.Column('updated_at',              sa.DateTime(), nullable=False),
        sa.Column('is_active',               sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',              UUID(as_uuid=True), nullable=False),
        sa.Column('created_by',              UUID(as_uuid=True), nullable=True),
        sa.Column('title',                   sa.String(255), nullable=False),
        sa.Column('content',                 sa.Text(), nullable=False),
        sa.Column('category',                notice_cat_e, nullable=False),
        sa.Column('priority',                notice_pri_e, nullable=False, server_default='normal'),
        sa.Column('status',                  notice_st_e,  nullable=False, server_default='draft'),
        sa.Column('publish_date',            sa.DateTime(), nullable=True),
        sa.Column('expiry_date',             sa.DateTime(), nullable=True),
        sa.Column('acknowledgement_required',sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('attachment_url',          sa.String(500), nullable=True),
        sa.Column('audience_type',           audience_e, nullable=False, server_default='all_residents'),
        sa.Column('target_wing_ids',         JSONB, nullable=True),
        sa.Column('target_flat_ids',         JSONB, nullable=True),
        sa.Column('target_user_ids',         JSONB, nullable=True),
        sa.Column('total_audience',          sa.Integer(), nullable=False, server_default='0'),
        sa.Column('acknowledgement_count',   sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_notices_id',          'notices', ['id'])
    op.create_index('ix_notices_society_id',  'notices', ['society_id'])
    op.create_index('ix_notices_category',    'notices', ['category'])
    op.create_index('ix_notices_priority',    'notices', ['priority'])
    op.create_index('ix_notices_status',      'notices', ['status'])
    op.create_index('ix_notices_audience',    'notices', ['audience_type'])

    # ── notice_acknowledgements ───────────────────────────────────────────────
    op.create_table('notice_acknowledgements',
        sa.Column('id',        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',sa.DateTime(), nullable=False),
        sa.Column('updated_at',sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notice_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',   UUID(as_uuid=True), nullable=True),
        sa.Column('ack_at',    sa.DateTime(), nullable=False),
        sa.Column('notes',     sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['notice_id'], ['notices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],   ['users.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],   ['flats.id'],   ondelete='SET NULL'),
    )
    op.create_index('ix_notice_acks_id',        'notice_acknowledgements', ['id'])
    op.create_index('ix_notice_acks_notice_id', 'notice_acknowledgements', ['notice_id'])
    op.create_index('ix_notice_acks_user_id',   'notice_acknowledgements', ['user_id'])

    # ── announcements ─────────────────────────────────────────────────────────
    op.create_table('announcements',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('created_by',   UUID(as_uuid=True), nullable=True),
        sa.Column('title',        sa.String(255), nullable=False),
        sa.Column('content',      sa.Text(), nullable=False),
        sa.Column('category',     notice_cat_e, nullable=False),
        sa.Column('priority',     notice_pri_e, nullable=False, server_default='normal'),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('publish_date', sa.DateTime(), nullable=True),
        sa.Column('expiry_date',  sa.DateTime(), nullable=True),
        sa.Column('image_url',    sa.String(500), nullable=True),
        sa.Column('audience_type',audience_e, nullable=False, server_default='all'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_announcements_id',         'announcements', ['id'])
    op.create_index('ix_announcements_society_id', 'announcements', ['society_id'])
    op.create_index('ix_announcements_published',  'announcements', ['is_published'])

    # ── communication_logs ────────────────────────────────────────────────────
    op.create_table('communication_logs',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id', UUID(as_uuid=True), nullable=False),
        sa.Column('notice_id',  UUID(as_uuid=True), nullable=True),
        sa.Column('user_id',    UUID(as_uuid=True), nullable=True),
        sa.Column('channel',    sa.String(30), nullable=False),
        sa.Column('status',     sa.String(30), nullable=False),
        sa.Column('sent_at',    sa.DateTime(), nullable=False),
        sa.Column('error_msg',  sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['notice_id'],  ['notices.id'],   ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'],    ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_communication_logs_id',         'communication_logs', ['id'])
    op.create_index('ix_communication_logs_society_id', 'communication_logs', ['society_id'])
    op.create_index('ix_communication_logs_notice_id',  'communication_logs', ['notice_id'])

    # ── emergency_alerts ──────────────────────────────────────────────────────
    op.create_table('emergency_alerts',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',          sa.DateTime(), nullable=False),
        sa.Column('updated_at',          sa.DateTime(), nullable=False),
        sa.Column('is_active',           sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('triggered_by',        UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_by',         UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type',          alert_type_e, nullable=False),
        sa.Column('status',              alert_st_e, nullable=False, server_default='active'),
        sa.Column('title',               sa.String(255), nullable=False),
        sa.Column('description',         sa.Text(), nullable=True),
        sa.Column('location',            sa.String(255), nullable=True),
        sa.Column('triggered_at',        sa.DateTime(), nullable=False),
        sa.Column('resolved_at',         sa.DateTime(), nullable=True),
        sa.Column('resolution_notes',    sa.Text(), nullable=True),
        sa.Column('notify_all_residents',sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_security',     sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_committee',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('push_sent',           sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sms_sent',            sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('whatsapp_sent',       sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['society_id'],   ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'],  ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_emergency_alerts_id',         'emergency_alerts', ['id'])
    op.create_index('ix_emergency_alerts_society_id', 'emergency_alerts', ['society_id'])
    op.create_index('ix_emergency_alerts_type',       'emergency_alerts', ['alert_type'])
    op.create_index('ix_emergency_alerts_status',     'emergency_alerts', ['status'])


def downgrade() -> None:
    for t in ['emergency_alerts','communication_logs','announcements',
              'notice_acknowledgements','notices',
              'parking_access_logs','parking_violations','visitor_parking',
              'parking_allocations','parking_slots','parking_floors','parking_zones']:
        op.drop_table(t)
    for e in ['alertstatus','alerttype','audiencetype','noticestatus','noticepriority',
              'noticecategory','accessmethod','accesstype','violationtype',
              'visitorparkingstatus','allocationstatus','slotstatus','slottype']:
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
