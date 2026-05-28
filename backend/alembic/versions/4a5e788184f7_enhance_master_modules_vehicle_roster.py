"""enhance_master_modules_vehicle_roster

Revision ID: 4a5e788184f7
Revises: 77057560a5fe
Create Date: 2026-05-26

Changes:
  ALTER: societies (society_code, timezone, settings)
  ALTER: flats (maintenance_status, parking_slot, kyc_verified)
  ALTER: residents (kyc fields, family_member_count, comm_preference, emergency contact)
  ALTER: tenants (agreement dates, kyc, police_verification, move_in/out)
  CREATE: vehicles
  CREATE: staff_rosters
  CREATE: staff_leave_balances
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '4a5e788184f7'
down_revision = '77057560a5fe'
branch_labels = None
depends_on    = None


def upgrade() -> None:

    # ── ALTER societies ───────────────────────────────────────────────────────
    op.add_column('societies', sa.Column('society_code', sa.String(20), nullable=True))
    op.add_column('societies', sa.Column('country', sa.String(50), server_default='India', nullable=True))
    op.add_column('societies', sa.Column('timezone', sa.String(50), server_default='Asia/Kolkata', nullable=False))
    op.add_column('societies', sa.Column('total_wings', sa.Integer(), nullable=True))
    op.add_column('societies', sa.Column('total_flats', sa.Integer(), nullable=True))
    op.add_column('societies', sa.Column('website', sa.String(255), nullable=True))
    op.add_column('societies', sa.Column('emergency_contact_name', sa.String(255), nullable=True))
    op.add_column('societies', sa.Column('emergency_contact_phone', sa.String(20), nullable=True))
    op.add_column('societies', sa.Column('maintenance_day', sa.Integer(), nullable=True))
    op.add_column('societies', sa.Column('late_fee_percent', sa.Integer(), nullable=True))
    op.add_column('societies', sa.Column('allow_tenant_portal', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('societies', sa.Column('require_visitor_approval', sa.Boolean(), server_default='true', nullable=False))
    op.create_index('ix_societies_society_code', 'societies', ['society_code'], unique=True)

    # ── ALTER flats ───────────────────────────────────────────────────────────
    maint_status = sa.Enum('clear','due','overdue','disputed', name='maintenanceflatstatus')
    maint_status.create(op.get_bind(), checkfirst=True)
    op.add_column('flats', sa.Column('maintenance_status', maint_status, server_default='clear', nullable=True))
    op.add_column('flats', sa.Column('parking_slot',  sa.String(20), nullable=True))
    op.add_column('flats', sa.Column('parking_slot_2',sa.String(20), nullable=True))
    op.add_column('flats', sa.Column('kyc_verified',  sa.Boolean(), server_default='false', nullable=False))
    op.add_column('flats', sa.Column('remarks',       sa.Text(), nullable=True))

    # ── ALTER residents ───────────────────────────────────────────────────────
    comm_pref = sa.Enum('app_only','sms','email','whatsapp','all', name='communicationpreference')
    comm_pref.create(op.get_bind(), checkfirst=True)
    op.add_column('residents', sa.Column('kyc_verified',             sa.Boolean(), server_default='false', nullable=False))
    op.add_column('residents', sa.Column('kyc_doc_url',              sa.String(500), nullable=True))
    op.add_column('residents', sa.Column('family_member_count',      sa.Integer(), server_default='0', nullable=False))
    op.add_column('residents', sa.Column('emergency_contact_name',   sa.String(255), nullable=True))
    op.add_column('residents', sa.Column('emergency_contact_phone',  sa.String(20), nullable=True))
    op.add_column('residents', sa.Column('comm_preference',          comm_pref, server_default='app_only', nullable=True))
    op.add_column('residents', sa.Column('photo_url',                sa.String(500), nullable=True))

    # ── ALTER tenants ─────────────────────────────────────────────────────────
    police_status = sa.Enum('pending','submitted','verified','rejected', name='policeverificationstatus')
    police_status.create(op.get_bind(), checkfirst=True)
    op.add_column('tenants', sa.Column('agreement_start_date',         sa.Date(), nullable=True))
    op.add_column('tenants', sa.Column('agreement_end_date',           sa.Date(), nullable=True))
    op.add_column('tenants', sa.Column('agreement_doc_url',            sa.String(500), nullable=True))
    op.add_column('tenants', sa.Column('kyc_verified',                 sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tenants', sa.Column('kyc_doc_url',                  sa.String(500), nullable=True))
    op.add_column('tenants', sa.Column('police_verification_status',   police_status, server_default='pending', nullable=True))
    op.add_column('tenants', sa.Column('police_verification_date',     sa.Date(), nullable=True))
    op.add_column('tenants', sa.Column('move_in_date',                 sa.Date(), nullable=True))
    op.add_column('tenants', sa.Column('move_out_date',                sa.Date(), nullable=True))
    op.add_column('tenants', sa.Column('remarks',                      sa.Text(), nullable=True))

    # ── CREATE vehicles ───────────────────────────────────────────────────────
    vehicle_type_enum = sa.Enum('car','motorcycle','scooter','auto','truck','van','bicycle','other', name='vehicletype')
    vehicle_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table('vehicles',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',          UUID(as_uuid=True), nullable=True),
        sa.Column('resident_id',      UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('registered_by',    UUID(as_uuid=True), nullable=True),
        sa.Column('vehicle_number',   sa.String(30), nullable=False),
        sa.Column('vehicle_type',     vehicle_type_enum, nullable=False, server_default='car'),
        sa.Column('make',             sa.String(100), nullable=True),
        sa.Column('model',            sa.String(100), nullable=True),
        sa.Column('color',            sa.String(50), nullable=True),
        sa.Column('year',             sa.String(4), nullable=True),
        sa.Column('parking_slot',     sa.String(20), nullable=True),
        sa.Column('rfid_tag',         sa.String(100), nullable=True),
        sa.Column('fasttag_number',   sa.String(50), nullable=True),
        sa.Column('insurance_expiry', sa.String(10), nullable=True),
        sa.Column('rc_number',        sa.String(50), nullable=True),
        sa.Column('remarks',          sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],   ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],      ['flats.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resident_id'],  ['residents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'],    ['tenants.id'],   ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['registered_by'],['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_vehicles_id',             'vehicles', ['id'])
    op.create_index('ix_vehicles_society_id',     'vehicles', ['society_id'])
    op.create_index('ix_vehicles_flat_id',        'vehicles', ['flat_id'])
    op.create_index('ix_vehicles_resident_id',    'vehicles', ['resident_id'])
    op.create_index('ix_vehicles_vehicle_number', 'vehicles', ['vehicle_number'])
    op.create_index('ix_vehicles_vehicle_type',   'vehicles', ['vehicle_type'])
    op.create_index('ix_vehicles_rfid_tag',       'vehicles', ['rfid_tag'], unique=True)
    op.create_index('ix_vehicles_parking_slot',   'vehicles', ['parking_slot'])

    # ── CREATE staff_rosters ──────────────────────────────────────────────────
    roster_status_enum = sa.Enum('draft','published','archived', name='rosterstatus')
    roster_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table('staff_rosters',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',      sa.DateTime(), nullable=False),
        sa.Column('updated_at',      sa.DateTime(), nullable=False),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',      UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',        UUID(as_uuid=True), nullable=False),
        sa.Column('shift_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('created_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('week_start',      sa.Date(), nullable=False),
        sa.Column('week_end',        sa.Date(), nullable=False),
        sa.Column('roster_status',   roster_status_enum, nullable=False, server_default='draft'),
        sa.Column('monday',          sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tuesday',         sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('wednesday',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('thursday',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('friday',          sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('saturday',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sunday',          sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_holiday_week', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes',           sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shift_id'],   ['staff_shifts.id'],ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],      ondelete='SET NULL'),
    )
    op.create_index('ix_staff_rosters_id',         'staff_rosters', ['id'])
    op.create_index('ix_staff_rosters_staff_id',   'staff_rosters', ['staff_id'])
    op.create_index('ix_staff_rosters_society_id', 'staff_rosters', ['society_id'])
    op.create_index('ix_staff_rosters_week_start', 'staff_rosters', ['week_start'])

    # ── CREATE staff_leave_balances ───────────────────────────────────────────
    op.create_table('staff_leave_balances',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('year',         sa.Integer(), nullable=False),
        sa.Column('casual_total', sa.Float(), nullable=False, server_default='12'),
        sa.Column('sick_total',   sa.Float(), nullable=False, server_default='12'),
        sa.Column('earned_total', sa.Float(), nullable=False, server_default='15'),
        sa.Column('casual_used',  sa.Float(), nullable=False, server_default='0'),
        sa.Column('sick_used',    sa.Float(), nullable=False, server_default='0'),
        sa.Column('earned_used',  sa.Float(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],     ondelete='CASCADE'),
    )
    op.create_index('ix_staff_leave_balances_id',       'staff_leave_balances', ['id'])
    op.create_index('ix_staff_leave_balances_staff_id', 'staff_leave_balances', ['staff_id'])
    op.create_index('ix_staff_leave_balances_year',     'staff_leave_balances', ['year'])


def downgrade() -> None:
    op.drop_table('staff_leave_balances')
    op.drop_table('staff_rosters')
    op.drop_table('vehicles')
    sa.Enum(name='rosterstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='vehicletype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='policeverificationstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='communicationpreference').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='maintenanceflatstatus').drop(op.get_bind(), checkfirst=True)

    # DROP added columns (downgrade cleanup)
    for col in ['society_code','country','timezone','total_wings','total_flats',
                'website','emergency_contact_name','emergency_contact_phone',
                'maintenance_day','late_fee_percent','allow_tenant_portal','require_visitor_approval']:
        op.drop_column('societies', col)
    for col in ['maintenance_status','parking_slot','parking_slot_2','kyc_verified','remarks']:
        op.drop_column('flats', col)
    for col in ['kyc_verified','kyc_doc_url','family_member_count','emergency_contact_name',
                'emergency_contact_phone','comm_preference','photo_url']:
        op.drop_column('residents', col)
    for col in ['agreement_start_date','agreement_end_date','agreement_doc_url','kyc_verified',
                'kyc_doc_url','police_verification_status','police_verification_date',
                'move_in_date','move_out_date','remarks']:
        op.drop_column('tenants', col)
