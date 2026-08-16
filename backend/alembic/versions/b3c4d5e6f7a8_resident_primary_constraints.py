"""resident_primary_constraints

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-15

Phase M1.2 — database integrity for the new Resident CRUD:

  1. At most one ACTIVE primary resident per flat: a partial unique index
     on residents(flat_id) WHERE is_primary AND is_active. Inactive
     (moved-out) residents are excluded, so a historical primary owner
     never blocks a new one from being set.
  2. A primary resident must be OWNER or CO_OWNER — a FAMILY or DEPENDENT
     row can never carry is_primary = true. Enforced as a CHECK constraint
     so this holds even for writes that bypass the application layer.

No backfill is required: Resident creation has had no reachable API/service
code path before this phase (confirmed via repo-wide grep — the only
`Resident(` construction anywhere was a dev seed script), so there is no
existing data that could violate either constraint.

Idempotency notes:
  - CREATE UNIQUE INDEX IF NOT EXISTS is natively idempotent in PostgreSQL
    for partial indexes (unlike ADD CONSTRAINT, no DO $$ guard needed).
  - The CHECK constraint uses the same DO $$ IF NOT EXISTS $$ guard pattern
    already established in a1b2c3d4e5f6 (constraints have no native
    IF NOT EXISTS in PostgreSQL).
  - resident_type enum labels ('owner', 'co_owner', ...) are the lowercase
    .value strings, matching values_callable on the model column and the
    'residenttype' PG enum created in 95390f45bba6 — verified directly
    against that migration, not assumed.
"""
from alembic import op
import sqlalchemy as sa

revision      = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_resident_primary_per_flat
        ON residents (flat_id)
        WHERE is_primary = true AND is_active = true
    """))

    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'residents'
                  AND constraint_name = 'ck_resident_primary_type'
            ) THEN
                ALTER TABLE residents
                    ADD CONSTRAINT ck_resident_primary_type
                    CHECK (is_primary IS NOT TRUE OR resident_type IN ('owner', 'co_owner'));
            END IF;
        END $$
    """))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE residents DROP CONSTRAINT IF EXISTS ck_resident_primary_type"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_resident_primary_per_flat"))
