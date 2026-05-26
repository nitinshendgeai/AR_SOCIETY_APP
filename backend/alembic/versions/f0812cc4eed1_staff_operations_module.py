"""staff_operations_module

Revision ID: f0812cc4eed1
Revises: a05bc0ded1e2
Create Date: 2026-05-23

Tables: staff_designations, staff_shifts, staff, duty_assignments,
        staff_attendance, staff_tasks, staff_leaves, staff_work_logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = 'f0812cc4eed1'
down_revision = 'a05bc0ded1e2'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    dept_enum   = sa.Enum('security','housekeeping','maintenance','electrical','plumbing','gardening','admin','amenities', name='staffdepartment')
    status_enum = sa.Enum('active','inactive','on_leave','terminated','probation', name='staffstatus')
    att_enum    = sa.Enum('present','absent','half_day','leave','overtime','off_duty', name='attendancestatus')
    task_enum   = sa.Enum('assigned','acknowledged','in_progress','completed','verified','cancelled', name='taskstatus')
    leave_type  = sa.Enum('casual','sick','earned','emergency','unpaid', name='leavetype')
    leave_status= sa.Enum('pending','approved','rejected','cancelled', name='leavestatus')
    shift_enum  = sa.Enum('morning','afternoon','night','general','custom', name='shifttype')

    # ── staff_designations ────────────────────────────────────────────────────
    op.create_table('staff_designations',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('name',        sa.String(100), nullable=False),
        sa.Column('department',  dept_enum, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_staff_designations_id',        'staff_designations', ['id'])
    op.create_index('ix_staff_designations_society_id','staff_designations', ['society_id'])
    op.create_index('ix_staff_designations_dept',      'staff_designations', ['department'])

    # ── staff_shifts ──────────────────────────────────────────────────────────
    op.create_table('staff_shifts',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('name',        sa.String(100), nullable=False),
        sa.Column('shift_type',  shift_enum, nullable=False, server_default='general'),
        sa.Column('start_time',  sa.Time(), nullable=False),
        sa.Column('end_time',    sa.Time(), nullable=False),
        sa.Column('is_overnight',sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_staff_shifts_id',        'staff_shifts', ['id'])
    op.create_index('ix_staff_shifts_society_id','staff_shifts', ['society_id'])

    # ── staff ─────────────────────────────────────────────────────────────────
    op.create_table('staff',
        sa.Column('id',                      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',              sa.DateTime(), nullable=False),
        sa.Column('updated_at',              sa.DateTime(), nullable=False),
        sa.Column('is_active',               sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',              UUID(as_uuid=True), nullable=False),
        sa.Column('user_id',                 UUID(as_uuid=True), nullable=True),
        sa.Column('employee_code',           sa.String(20), nullable=False),
        sa.Column('full_name',               sa.String(255), nullable=False),
        sa.Column('mobile',                  sa.String(20), nullable=False),
        sa.Column('email',                   sa.String(255), nullable=True),
        sa.Column('photo_url',               sa.String(500), nullable=True),
        sa.Column('department',              dept_enum, nullable=False),
        sa.Column('designation_id',          UUID(as_uuid=True), nullable=True),
        sa.Column('shift_id',                UUID(as_uuid=True), nullable=True),
        sa.Column('status',                  status_enum, nullable=False, server_default='probation'),
        sa.Column('joining_date',            sa.Date(), nullable=True),
        sa.Column('termination_date',        sa.Date(), nullable=True),
        sa.Column('emergency_contact_name',  sa.String(255), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(20), nullable=True),
        sa.Column('bank_account_number',     sa.String(50), nullable=True),
        sa.Column('bank_name',               sa.String(100), nullable=True),
        sa.Column('base_salary',             sa.Float(), nullable=True),
        sa.Column('pf_number',               sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],    ['societies.id'],       ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],       ['users.id'],           ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['designation_id'],['staff_designations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['shift_id'],      ['staff_shifts.id'],    ondelete='SET NULL'),
    )
    op.create_index('ix_staff_id',            'staff', ['id'])
    op.create_index('ix_staff_employee_code', 'staff', ['employee_code'], unique=True)
    op.create_index('ix_staff_society_id',    'staff', ['society_id'])
    op.create_index('ix_staff_user_id',       'staff', ['user_id'])
    op.create_index('ix_staff_mobile',        'staff', ['mobile'])
    op.create_index('ix_staff_department',    'staff', ['department'])
    op.create_index('ix_staff_status',        'staff', ['status'])

    # ── duty_assignments ──────────────────────────────────────────────────────
    op.create_table('duty_assignments',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('shift_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_by',  UUID(as_uuid=True), nullable=True),
        sa.Column('duty_name',    sa.String(255), nullable=False),
        sa.Column('description',  sa.Text(), nullable=True),
        sa.Column('location',     sa.String(255), nullable=True),
        sa.Column('duty_date',    sa.Date(), nullable=False),
        sa.Column('start_time',   sa.Time(), nullable=True),
        sa.Column('end_time',     sa.Time(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by',  UUID(as_uuid=True), nullable=True),
        sa.Column('verified_at',  sa.DateTime(), nullable=True),
        sa.Column('notes',        sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],    ['staff.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shift_id'],    ['staff_shifts.id'],ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'],      ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'],      ondelete='SET NULL'),
    )
    op.create_index('ix_duty_assignments_id',        'duty_assignments', ['id'])
    op.create_index('ix_duty_assignments_staff_id',  'duty_assignments', ['staff_id'])
    op.create_index('ix_duty_assignments_society_id','duty_assignments', ['society_id'])
    op.create_index('ix_duty_assignments_date',      'duty_assignments', ['duty_date'])

    # ── staff_attendance ──────────────────────────────────────────────────────
    op.create_table('staff_attendance',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('attendance_date',  sa.Date(), nullable=False),
        sa.Column('status',           att_enum, nullable=False, server_default='present'),
        sa.Column('check_in_time',    sa.DateTime(), nullable=True),
        sa.Column('check_out_time',   sa.DateTime(), nullable=True),
        sa.Column('working_hours',    sa.Float(), nullable=True),
        sa.Column('overtime_hours',   sa.Float(), nullable=True),
        sa.Column('is_manual_entry',  sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('marked_by',        UUID(as_uuid=True), nullable=True),
        sa.Column('notes',            sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['marked_by'],  ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_staff_attendance_id',        'staff_attendance', ['id'])
    op.create_index('ix_staff_attendance_staff_id',  'staff_attendance', ['staff_id'])
    op.create_index('ix_staff_attendance_society_id','staff_attendance', ['society_id'])
    op.create_index('ix_staff_attendance_date',      'staff_attendance', ['attendance_date'])
    op.create_index('ix_staff_attendance_status',    'staff_attendance', ['status'])

    # ── staff_tasks ───────────────────────────────────────────────────────────
    op.create_table('staff_tasks',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('verified_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('complaint_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('visitor_id',       UUID(as_uuid=True), nullable=True),
        sa.Column('title',            sa.String(255), nullable=False),
        sa.Column('description',      sa.Text(), nullable=True),
        sa.Column('location',         sa.String(255), nullable=True),
        sa.Column('due_date',         sa.DateTime(), nullable=True),
        sa.Column('status',           task_enum, nullable=False, server_default='assigned'),
        sa.Column('acknowledged_at',  sa.DateTime(), nullable=True),
        sa.Column('started_at',       sa.DateTime(), nullable=True),
        sa.Column('completed_at',     sa.DateTime(), nullable=True),
        sa.Column('verified_at',      sa.DateTime(), nullable=True),
        sa.Column('completion_notes', sa.Text(), nullable=True),
        sa.Column('priority',         sa.String(20), nullable=False, server_default='medium'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'],['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verified_by'],['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_staff_tasks_id',        'staff_tasks', ['id'])
    op.create_index('ix_staff_tasks_staff_id',  'staff_tasks', ['staff_id'])
    op.create_index('ix_staff_tasks_society_id','staff_tasks', ['society_id'])
    op.create_index('ix_staff_tasks_status',    'staff_tasks', ['status'])

    # ── staff_leaves ──────────────────────────────────────────────────────────
    op.create_table('staff_leaves',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('approved_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('leave_type',       leave_type, nullable=False),
        sa.Column('from_date',        sa.Date(), nullable=False),
        sa.Column('to_date',          sa.Date(), nullable=False),
        sa.Column('total_days',       sa.Integer(), nullable=False),
        sa.Column('reason',           sa.Text(), nullable=True),
        sa.Column('status',           leave_status, nullable=False, server_default='pending'),
        sa.Column('approved_at',      sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'],['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_staff_leaves_id',        'staff_leaves', ['id'])
    op.create_index('ix_staff_leaves_staff_id',  'staff_leaves', ['staff_id'])
    op.create_index('ix_staff_leaves_society_id','staff_leaves', ['society_id'])
    op.create_index('ix_staff_leaves_status',    'staff_leaves', ['status'])
    op.create_index('ix_staff_leaves_type',      'staff_leaves', ['leave_type'])

    # ── staff_work_logs ───────────────────────────────────────────────────────
    op.create_table('staff_work_logs',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id', UUID(as_uuid=True), nullable=False),
        sa.Column('staff_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('task_id',    UUID(as_uuid=True), nullable=True),
        sa.Column('notes',      sa.Text(), nullable=False),
        sa.Column('logged_at',  sa.DateTime(), nullable=False),
        sa.Column('photos_url', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'],   ['staff.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'],    ['staff_tasks.id'],ondelete='CASCADE'),
    )
    op.create_index('ix_staff_work_logs_id',       'staff_work_logs', ['id'])
    op.create_index('ix_staff_work_logs_staff_id', 'staff_work_logs', ['staff_id'])
    op.create_index('ix_staff_work_logs_task_id',  'staff_work_logs', ['task_id'])


def downgrade() -> None:
    op.drop_table('staff_work_logs')
    op.drop_table('staff_leaves')
    op.drop_table('staff_tasks')
    op.drop_table('staff_attendance')
    op.drop_table('duty_assignments')
    op.drop_table('staff')
    op.drop_table('staff_shifts')
    op.drop_table('staff_designations')
    for e in ['leavestatus','leavetype','taskstatus','attendancestatus','staffstatus','staffdepartment','shifttype']:
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
