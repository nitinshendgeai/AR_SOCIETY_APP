"""agreement_renewal_fk

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-15

Phase M1.3 — promotes agreement_tracker.renewal_of_id from a bare UUID
column to a real self-referential foreign key, so the renewal chain
(Phase M1.3 OccupancyService.renew_agreement) has referential integrity
instead of relying on application code alone.

Preflight: before adding the constraint, checks for any existing
renewal_of_id value that doesn't point at a real agreement_tracker row
(orphaned reference — would make ADD CONSTRAINT fail anyway, but this
gives a clear, actionable error instead of a raw Postgres FK-violation
message). Aborts the migration (raises, no partial state) if any are
found rather than silently dropping/nulling them.
"""
from alembic import op
import sqlalchemy as sa

revision      = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    conn = op.get_bind()

    orphans = conn.execute(sa.text("""
        SELECT a.id, a.renewal_of_id
        FROM agreement_tracker a
        WHERE a.renewal_of_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM agreement_tracker p WHERE p.id = a.renewal_of_id)
    """)).fetchall()
    if orphans:
        ids = ", ".join(str(row[0]) for row in orphans)
        raise RuntimeError(
            f"agreement_renewal_fk preflight BLOCKED: {len(orphans)} agreement_tracker "
            f"row(s) have a renewal_of_id that doesn't reference an existing row: {ids}. "
            "Not adding the FK — resolve these rows (null out the dangling renewal_of_id "
            "or fix the reference) before re-running this migration."
        )

    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'agreement_tracker'
                  AND constraint_name = 'fk_agreement_tracker_renewal_of_id'
            ) THEN
                ALTER TABLE agreement_tracker
                    ADD CONSTRAINT fk_agreement_tracker_renewal_of_id
                    FOREIGN KEY (renewal_of_id) REFERENCES agreement_tracker(id)
                    ON DELETE SET NULL;
            END IF;
        END $$
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE agreement_tracker DROP CONSTRAINT IF EXISTS fk_agreement_tracker_renewal_of_id"
    ))
