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

Uses IF NOT EXISTS throughout — the complaint migration right before this
one turned out to hit a database that already had one of its two new
columns from undocumented prior drift and not the other, so this one
makes no assumption about which of these four are already present.
"""
from alembic import op
import sqlalchemy as sa

revision      = '7c8d9e0f1a2b'
down_revision = '929e06280933'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE staff_attendance ADD COLUMN IF NOT EXISTS "
        "is_approved BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE staff_attendance ADD COLUMN IF NOT EXISTS approved_by UUID"
    ))
    op.execute(sa.text(
        "ALTER TABLE staff_attendance ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP"
    ))
    op.execute(sa.text(
        "ALTER TABLE staff_attendance ADD COLUMN IF NOT EXISTS approval_notes TEXT"
    ))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'staff_attendance'
                  AND constraint_name = 'fk_staff_attendance_approved_by_users'
            ) THEN
                ALTER TABLE staff_attendance
                    ADD CONSTRAINT fk_staff_attendance_approved_by_users
                    FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END $$
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_staff_attendance_is_approved "
        "ON staff_attendance (is_approved)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_staff_attendance_is_approved"))
    op.execute(sa.text(
        "ALTER TABLE staff_attendance DROP CONSTRAINT IF EXISTS fk_staff_attendance_approved_by_users"
    ))
    op.execute(sa.text("ALTER TABLE staff_attendance DROP COLUMN IF EXISTS approval_notes"))
    op.execute(sa.text("ALTER TABLE staff_attendance DROP COLUMN IF EXISTS approved_at"))
    op.execute(sa.text("ALTER TABLE staff_attendance DROP COLUMN IF EXISTS approved_by"))
    op.execute(sa.text("ALTER TABLE staff_attendance DROP COLUMN IF EXISTS is_approved"))
