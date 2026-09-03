"""staff_attendance_approval_columns

Revision ID: 7c8d9e0f1a2b
Revises: 929e06280933
Create Date: 2026-09-03

Second instance of the same schema-drift class as 929e06280933: the
StaffAttendance model (app/modules/staff/models/staff.py) declares
is_approved/approved_by/approved_at/approval_notes (the check-in approval
flow, distinct from the already-migrated checkout_* columns), and
StaffService.approve_attendance()/reject_attendance() write to them — but
the original staff_operations_module migration (f0812cc4eed1) never
created them. Same SQLite-vs-Postgres blind spot: passes in tests, 500s
on approve/reject against a real deployed database.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = '7c8d9e0f1a2b'
down_revision = '929e06280933'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column('staff_attendance', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('staff_attendance', sa.Column('approved_by', UUID(as_uuid=True), nullable=True))
    op.add_column('staff_attendance', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('staff_attendance', sa.Column('approval_notes', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_staff_attendance_approved_by_users', 'staff_attendance', 'users',
        ['approved_by'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_staff_attendance_is_approved', 'staff_attendance', ['is_approved'])


def downgrade() -> None:
    op.drop_index('ix_staff_attendance_is_approved', table_name='staff_attendance')
    op.drop_constraint('fk_staff_attendance_approved_by_users', 'staff_attendance', type_='foreignkey')
    op.drop_column('staff_attendance', 'approval_notes')
    op.drop_column('staff_attendance', 'approved_at')
    op.drop_column('staff_attendance', 'approved_by')
    op.drop_column('staff_attendance', 'is_approved')
