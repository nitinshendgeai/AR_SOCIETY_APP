"""complaint_assigned_by_column

Revision ID: 929e06280933
Revises: f7a8b9c0d1e2
Create Date: 2026-09-03

Fixes a schema-drift bug: the Complaint model (app/modules/complaint/models/
complaint.py) declares `assigned_by` and `assigned_department` columns, and
ComplaintService.create_complaint()/assign_complaint() write to
`assigned_by` on every complaint creation that auto-assigns to a Manager —
but the original complaint_management_module migration (aab340f2f215) never
created either column. SQLite's test schema is built straight from the
model (Base.metadata.create_all()) so this never surfaced there; on the
real Postgres database (schema from migrations only, plus whatever ad-hoc
drift has already happened — production turned out to already have
`assigned_department` from some earlier undocumented change but not
`assigned_by`) every complaint create/assign that touches `assigned_by`
fails with "column does not exist", surfacing to the app as a 500 on save.

Uses IF NOT EXISTS throughout (matching the established idiom in
a1b2c3d4e5f6_society_structure_wings_floors_flats.py) rather than plain
op.add_column, since a first attempt at this migration proved the two
columns' presence on the real database can't be assumed equally — the
one thing this migration must not do is fail outright because one of the
two already exists while the other (the one actually causing the crash)
does not.
"""
from alembic import op
import sqlalchemy as sa

revision      = '929e06280933'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS assigned_by UUID"
    ))
    op.execute(sa.text(
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS assigned_department VARCHAR(50)"
    ))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'complaints'
                  AND constraint_name = 'fk_complaints_assigned_by_users'
            ) THEN
                ALTER TABLE complaints
                    ADD CONSTRAINT fk_complaints_assigned_by_users
                    FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END $$
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_complaints_assigned_department "
        "ON complaints (assigned_department)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_complaints_assigned_department"))
    op.execute(sa.text(
        "ALTER TABLE complaints DROP CONSTRAINT IF EXISTS fk_complaints_assigned_by_users"
    ))
    op.execute(sa.text("ALTER TABLE complaints DROP COLUMN IF EXISTS assigned_department"))
    op.execute(sa.text("ALTER TABLE complaints DROP COLUMN IF EXISTS assigned_by"))
