"""resident_unique_name_per_flat

Revision ID: c5f7b9d1e3a5
Revises: c4e6a8b0d2f4
Create Date: 2026-10-25

At most one ACTIVE resident of a given type with a given name per flat (name compared
ignoring case and surrounding spaces). Backs up the check in ResidentService.create so a
bulk import run twice cannot double the residents even if it bypasses the service.

Existing duplicates must be cleaned up first: the migration stops with a list of them
instead of failing part-way. Idempotent (CREATE UNIQUE INDEX IF NOT EXISTS).
"""
from alembic import op
import sqlalchemy as sa

revision      = 'c5f7b9d1e3a5'
down_revision = 'c4e6a8b0d2f4'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    dups = bind.execute(sa.text("""
        SELECT w.name, f.flat_number, lower(btrim(r.full_name)) AS name, r.resident_type, COUNT(*) AS copies
        FROM residents r
        JOIN flats f ON f.id = r.flat_id
        JOIN wings w ON w.id = f.wing_id
        WHERE r.is_active
        GROUP BY w.name, f.flat_number, r.flat_id, lower(btrim(r.full_name)), r.resident_type
        HAVING COUNT(*) > 1
        ORDER BY 1, 2
    """)).fetchall()
    if dups:
        listing = "; ".join(f"{d[0]}-{d[1]} '{d[2]}' ({d[3]}) x{d[4]}" for d in dups[:20])
        raise RuntimeError(
            f"{len(dups)} flat(s) have duplicate active residents; remove the extra rows "
            f"(keep one each) and run this migration again. First: {listing}"
        )
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_resident_name_per_flat
        ON residents (flat_id, lower(btrim(full_name)), resident_type)
        WHERE is_active = true
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_resident_name_per_flat"))
