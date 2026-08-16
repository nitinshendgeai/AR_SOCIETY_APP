"""agreement_occupancy_society_not_null

Revision ID: a2b3c4d5e6f7
Revises: f1g2h3i4j5k6
Create Date: 2026-08-15

Fixes a model/DB drift: agreement_tracker.society_id and
occupancy_logs.society_id are declared nullable=False in the SQLAlchemy
models (agreement_tracker.py, occupancy_log.py) but were created
nullable=True by 31b688f5de60. That mismatch is what let
OccupancyService.tenant_move_in() insert AgreementTracker rows with a
hardcoded society_id=None (now fixed in application code) without the
database ever rejecting them — and since get_expiring_agreements() filters
on society_id, every agreement created that way was permanently invisible
to that query.

Changes:
  - Backfill any existing NULL society_id on agreement_tracker / occupancy_logs
    by deriving it from flat_id -> flats.wing_id -> wings.society_id.
  - ALTER COLUMN ... SET NOT NULL on both tables, to match the models.

Idempotency notes:
  - The UPDATE only touches rows where society_id IS NULL, so re-running
    this migration is a no-op on a database that's already been backfilled.
  - SET NOT NULL is naturally idempotent in PostgreSQL (no error if the
    column is already NOT NULL).
"""
from alembic import op
import sqlalchemy as sa

revision      = 'a2b3c4d5e6f7'
down_revision = 'f1g2h3i4j5k6'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── Backfill agreement_tracker.society_id from its flat's wing ───────────
    op.execute(sa.text("""
        UPDATE agreement_tracker AS at
        SET society_id = w.society_id
        FROM flats f
        JOIN wings w ON w.id = f.wing_id
        WHERE at.flat_id = f.id AND at.society_id IS NULL
    """))

    # ── Backfill occupancy_logs.society_id the same way ───────────────────────
    # (application code already derives this correctly on write; this is a
    # safety net for any row that predates that logic or was written outside it)
    op.execute(sa.text("""
        UPDATE occupancy_logs AS ol
        SET society_id = w.society_id
        FROM flats f
        JOIN wings w ON w.id = f.wing_id
        WHERE ol.flat_id = f.id AND ol.society_id IS NULL
    """))

    op.alter_column('agreement_tracker', 'society_id', nullable=False)
    op.alter_column('occupancy_logs', 'society_id', nullable=False)


def downgrade() -> None:
    op.alter_column('occupancy_logs', 'society_id', nullable=True)
    op.alter_column('agreement_tracker', 'society_id', nullable=True)
