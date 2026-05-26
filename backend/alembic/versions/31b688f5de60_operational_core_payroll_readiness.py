"""operational_core_payroll_readiness

Revision ID: 31b688f5de60
Revises: 4a5e788184f7
Create Date: 2026-05-26

Tables:
  CREATE: occupancy_logs, agreement_tracker
  CREATE: staff_salary_structures, attendance_corrections, monthly_attendance_summaries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '31b688f5de60'
down_revision = '4a5e788184f7'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    occupancy_event = sa.Enum(
        'resident_move_in','resident_move_out','tenant_move_in','tenant_move_out',
        'flat_vacant','ownership_transfer', name='occupancyeventtype'
    )
    agreement_status = sa.Enum('active','expired','renewed','terminated', name='agreementstatus')
    payroll_cycle    = sa.Enum('monthly','weekly','fortnightly', name='payrollcycle')
    correction_status= sa.Enum('pending','approved','rejected', name='attendancecorrectionstatus')

    # ── occupancy_logs ────────────────────────────────────────────────────────
    op.create_table('occupancy_logs',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=True),
        sa.Column('flat_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('wing_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('resident_id', UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id',   UUID(as_uuid=True), nullable=True),
        sa.Column('event_type',  occupancy_event, nullable=False),
        sa.Column('event_date',  sa.Date(), nullable=False),
        sa.Column('logged_by',   UUID(as_uuid=True), nullable=True),
        sa.Column('notes',       sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['wing_id'],     ['wings.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resident_id'], ['residents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'],   ['tenants.id'],   ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['logged_by'],   ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_occupancy_logs_id',          'occupancy_logs', ['id'])
    op.create_index('ix_occupancy_logs_flat_id',     'occupancy_logs', ['flat_id'])
    op.create_index('ix_occupancy_logs_resident_id', 'occupancy_logs', ['resident_id'])
    op.create_index('ix_occupancy_logs_tenant_id',   'occupancy_logs', ['tenant_id'])
    op.create_index('ix_occupancy_logs_event_type',  'occupancy_logs', ['event_type'])
    op.create_index('ix_occupancy_logs_event_date',  'occupancy_logs', ['event_date'])

    # ── agreement_tracker ─────────────────────────────────────────────────────
    op.create_table('agreement_tracker',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',        sa.DateTime(), nullable=False),
        sa.Column('updated_at',        sa.DateTime(), nullable=False),
        sa.Column('is_active',         sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('flat_id',           UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('resident_id',       UUID(as_uuid=True), nullable=True),
        sa.Column('agreement_number',  sa.String(50), nullable=True),
        sa.Column('start_date',        sa.Date(), nullable=False),
        sa.Column('end_date',          sa.Date(), nullable=False),
        sa.Column('monthly_rent',      sa.Numeric(12,2), nullable=True),
        sa.Column('security_deposit',  sa.Numeric(12,2), nullable=True),
        sa.Column('status',            agreement_status, nullable=False, server_default='active'),
        sa.Column('document_url',      sa.String(500), nullable=True),
        sa.Column('renewal_of_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('termination_reason',sa.Text(), nullable=True),
        sa.Column('alert_sent_30',     sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('alert_sent_7',      sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by',        UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'],   ['tenants.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resident_id'], ['residents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'],  ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_agreement_tracker_id',        'agreement_tracker', ['id'])
    op.create_index('ix_agreement_tracker_flat_id',   'agreement_tracker', ['flat_id'])
    op.create_index('ix_agreement_tracker_tenant_id', 'agreement_tracker', ['tenant_id'])
    op.create_index('ix_agreement_tracker_end_date',  'agreement_tracker', ['end_date'])
    op.create_index('ix_agreement_tracker_status',    'agreement_tracker', ['status'])
    op.create_index('ix_agreement_tracker_number',    'agreement_tracker', ['agreement_number'])

    # ── staff_salary_structures ───────────────────────────────────────────────
    op.create_table('staff_salary_structures',
        sa.Column('id',                    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',            sa.DateTime(), nullable=False),
        sa.Column('updated_at',            sa.DateTime(), nullable=False),
        sa.Column('is_active',             sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',            UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',              UUID(as_uuid=True), nullable=False),
        sa.Column('effective_from',        sa.Date(), nullable=False),
        sa.Column('effective_to',          sa.Date(), nullable=True),
        sa.Column('payroll_cycle',         payroll_cycle, nullable=False, server_default='monthly'),
        sa.Column('basic_salary',          sa.Numeric(10,2), nullable=False),
        sa.Column('hra',                   sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('conveyance',            sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('medical',               sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('special_allowance',     sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('shift_allowance',       sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('pf_employee_pct',       sa.Float(), nullable=False, server_default='12'),
        sa.Column('esi_employee_pct',      sa.Float(), nullable=False, server_default='0.75'),
        sa.Column('tds_monthly',           sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('overtime_rate_per_hour',sa.Numeric(8,2), nullable=True),
        sa.Column('working_days_per_month',sa.Integer(), nullable=False, server_default='26'),
        sa.Column('paid_leaves_per_year',  sa.Integer(), nullable=False, server_default='12'),
        sa.Column('created_by',            UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_staff_salary_structures_id',       'staff_salary_structures', ['id'])
    op.create_index('ix_staff_salary_structures_staff_id', 'staff_salary_structures', ['staff_id'])

    # ── attendance_corrections ────────────────────────────────────────────────
    op.create_table('attendance_corrections',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',          sa.DateTime(), nullable=False),
        sa.Column('updated_at',          sa.DateTime(), nullable=False),
        sa.Column('is_active',           sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',            UUID(as_uuid=True), nullable=False),
        sa.Column('attendance_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('requested_by',        UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by',         UUID(as_uuid=True), nullable=True),
        sa.Column('correction_date',     sa.Date(), nullable=False),
        sa.Column('original_status',     sa.String(50), nullable=True),
        sa.Column('requested_status',    sa.String(50), nullable=False),
        sa.Column('original_check_in',   sa.String(20), nullable=True),
        sa.Column('requested_check_in',  sa.String(20), nullable=True),
        sa.Column('original_check_out',  sa.String(20), nullable=True),
        sa.Column('requested_check_out', sa.String(20), nullable=True),
        sa.Column('reason',              sa.Text(), nullable=False),
        sa.Column('status',              correction_status, nullable=False, server_default='pending'),
        sa.Column('rejection_reason',    sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],    ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],      ['staff.id'],          ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['attendance_id'], ['staff_attendance.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by'],  ['users.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'],   ['users.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_attendance_corrections_id',        'attendance_corrections', ['id'])
    op.create_index('ix_attendance_corrections_staff_id',  'attendance_corrections', ['staff_id'])
    op.create_index('ix_attendance_corrections_date',      'attendance_corrections', ['correction_date'])
    op.create_index('ix_attendance_corrections_status',    'attendance_corrections', ['status'])

    # ── monthly_attendance_summaries ──────────────────────────────────────────
    op.create_table('monthly_attendance_summaries',
        sa.Column('id',                    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',            sa.DateTime(), nullable=False),
        sa.Column('updated_at',            sa.DateTime(), nullable=False),
        sa.Column('is_active',             sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',            UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',              UUID(as_uuid=True), nullable=False),
        sa.Column('year',                  sa.Integer(), nullable=False),
        sa.Column('month',                 sa.Integer(), nullable=False),
        sa.Column('present_days',          sa.Integer(), nullable=False, server_default='0'),
        sa.Column('absent_days',           sa.Integer(), nullable=False, server_default='0'),
        sa.Column('half_day_count',        sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leave_days',            sa.Integer(), nullable=False, server_default='0'),
        sa.Column('holiday_days',          sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overtime_days',         sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_working_hours',   sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_overtime_hours',  sa.Float(), nullable=False, server_default='0'),
        sa.Column('late_arrivals',         sa.Integer(), nullable=False, server_default='0'),
        sa.Column('early_departures',      sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_finalized',          sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('finalized_by',          UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],   ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],     ['staff.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['finalized_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_monthly_att_summaries_id',       'monthly_attendance_summaries', ['id'])
    op.create_index('ix_monthly_att_summaries_staff_id', 'monthly_attendance_summaries', ['staff_id'])
    op.create_index('ix_monthly_att_summaries_year',     'monthly_attendance_summaries', ['year'])
    op.create_index('ix_monthly_att_summaries_month',    'monthly_attendance_summaries', ['month'])


def downgrade() -> None:
    op.drop_table('monthly_attendance_summaries')
    op.drop_table('attendance_corrections')
    op.drop_table('staff_salary_structures')
    op.drop_table('agreement_tracker')
    op.drop_table('occupancy_logs')
    for e in ['attendancecorrectionstatus','payrollcycle','agreementstatus','occupancyeventtype']:
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
