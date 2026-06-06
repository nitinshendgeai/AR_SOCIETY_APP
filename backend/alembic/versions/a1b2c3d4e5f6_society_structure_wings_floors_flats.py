"""society_structure_wings_floors_flats

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-06-06

Changes:
  ALTER societies: add registration_number, gst_number, pan_number
  ALTER wings: add description column, unique constraints on (society_id, name) and (society_id, code)
  CREATE floors: floor_number, floor_name, wing_id, society_id with unique constraint

Idempotency notes:
  - All ADD COLUMN operations use ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+)
  - Unique constraints guarded by DO $$ IF NOT EXISTS $$ blocks
  - CREATE TABLE IF NOT EXISTS for floors
  - CREATE INDEX IF NOT EXISTS for all floor indexes
  - Root cause of original failure: op.create_table() with index=True on wing_id/society_id
    auto-created ix_floors_wing_id and ix_floors_society_id; subsequent explicit
    op.create_index() calls then failed with "relation already exists".
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = 'a1b2c3d4e5f6'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on    = None


def upgrade() -> None:

    # ── ALTER societies: legal fields ─────────────────────────────────────────
    # ADD COLUMN IF NOT EXISTS is safe on fresh, partial, and complete DBs.
    op.execute(sa.text(
        "ALTER TABLE societies "
        "ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100)"
    ))
    op.execute(sa.text(
        "ALTER TABLE societies "
        "ADD COLUMN IF NOT EXISTS gst_number VARCHAR(20)"
    ))
    op.execute(sa.text(
        "ALTER TABLE societies "
        "ADD COLUMN IF NOT EXISTS pan_number VARCHAR(20)"
    ))

    # ── ALTER wings: add description ──────────────────────────────────────────
    op.execute(sa.text(
        "ALTER TABLE wings ADD COLUMN IF NOT EXISTS description TEXT"
    ))

    # ── Unique constraints on wings ───────────────────────────────────────────
    # PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS syntax; use a DO block.
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'wings'
                  AND constraint_name = 'uq_wing_society_name'
            ) THEN
                ALTER TABLE wings
                    ADD CONSTRAINT uq_wing_society_name UNIQUE (society_id, name);
            END IF;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'wings'
                  AND constraint_name = 'uq_wing_society_code'
            ) THEN
                ALTER TABLE wings
                    ADD CONSTRAINT uq_wing_society_code UNIQUE (society_id, code);
            END IF;
        END $$
    """))

    # ── CREATE floors table ───────────────────────────────────────────────────
    # Raw SQL so we can use IF NOT EXISTS.
    # Deliberately NO index=True on any column here — indexes are created
    # explicitly below using CREATE INDEX IF NOT EXISTS.  The original failure
    # was caused by index=True inside op.create_table(), which made SQLAlchemy
    # auto-create ix_floors_wing_id/ix_floors_society_id, and then the
    # explicit op.create_index() calls below tried to create them again.
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS floors (
            id           UUID         NOT NULL,
            created_at   TIMESTAMP    NOT NULL,
            updated_at   TIMESTAMP    NOT NULL,
            is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
            floor_number INTEGER      NOT NULL,
            floor_name   VARCHAR(50),
            wing_id      UUID         NOT NULL
                             REFERENCES wings(id) ON DELETE CASCADE,
            society_id   UUID         NOT NULL
                             REFERENCES societies(id) ON DELETE CASCADE,
            CONSTRAINT floors_pkey PRIMARY KEY (id)
        )
    """))

    # ── Unique constraint on floors ───────────────────────────────────────────
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'floors'
                  AND constraint_name = 'uq_floor_wing_number'
            ) THEN
                ALTER TABLE floors
                    ADD CONSTRAINT uq_floor_wing_number
                    UNIQUE (wing_id, floor_number);
            END IF;
        END $$
    """))

    # ── Indexes on floors ─────────────────────────────────────────────────────
    # CREATE INDEX IF NOT EXISTS is idempotent regardless of how the index
    # was created (auto by create_table index=True, or explicit).
    # ix_floors_id is omitted: id is a PRIMARY KEY and already has an implicit
    # index (floors_pkey); a separate ix_floors_id is redundant.
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_floors_wing_id "
        "ON floors (wing_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_floors_society_id "
        "ON floors (society_id)"
    ))


def downgrade() -> None:
    op.drop_table('floors')

    op.drop_constraint('uq_wing_society_code', 'wings', type_='unique')
    op.drop_constraint('uq_wing_society_name', 'wings', type_='unique')
    op.drop_column('wings', 'description')

    op.drop_column('societies', 'pan_number')
    op.drop_column('societies', 'gst_number')
    op.drop_column('societies', 'registration_number')
