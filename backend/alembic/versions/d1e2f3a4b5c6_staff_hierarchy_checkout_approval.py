"""Staff hierarchy, TECHNICAL/GYM departments, checkout approval fields

Revision ID: d1e2f3a4b5c6
Revises: f0812cc4eed1
Create Date: 2026-06-10

Changes:
- staff.reporting_manager_id FK to users
- staff_attendance.is_checkout_approved, checkout_approved_by, checkout_approved_at
- Extend staff_department enum with 'technical', 'gym'
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd1e2f3a4b5c6'
down_revision = 'f0812cc4eed1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend the staff_department enum with new values
    op.execute("ALTER TYPE staffdepartment ADD VALUE IF NOT EXISTS 'technical'")
    op.execute("ALTER TYPE staffdepartment ADD VALUE IF NOT EXISTS 'gym'")

    # Add reporting_manager_id to staff table
    op.add_column('staff', sa.Column(
        'reporting_manager_id',
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    ))

    # Add punch-out approval fields to staff_attendance
    op.add_column('staff_attendance', sa.Column('is_checkout_approved', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('staff_attendance', sa.Column('checkout_approved_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('staff_attendance', sa.Column('checkout_approved_at', sa.DateTime(), nullable=True))
    op.add_column('staff_attendance', sa.Column('checkout_approval_notes', sa.Text(), nullable=True))

    # Add department assignment to complaints
    op.add_column('complaints', sa.Column('assigned_department', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('complaints', 'assigned_department')
    op.drop_column('staff_attendance', 'checkout_approval_notes')
    op.drop_column('staff_attendance', 'checkout_approved_at')
    op.drop_column('staff_attendance', 'checkout_approved_by')
    op.drop_column('staff_attendance', 'is_checkout_approved')
    op.drop_column('staff', 'reporting_manager_id')
    # Enum values cannot be removed in PostgreSQL without dropping/recreating the type
