"""vehicle_constraints_with_preflight

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-15

Phase M1.3 — Vehicle hardening, database layer. Phase M1.2 added
application-level XOR validation (resident_id/tenant_id can't both be
set) and per-society duplicate-vehicle-number checking, but neither was
backed by a database constraint, so both were still race-condition-prone
and bypassable via any write path that isn't the API.

Unlike Resident/Tenant/AgreementTracker (which realistically have ~zero
production rows, since no code path could create them before M1.2/M1.3),
Vehicle has had a working, reachable creation endpoint since long before
this phase — so, per the M1.1 plan and the M1.3 brief, this migration
does NOT blindly ADD CONSTRAINT. It runs a preflight check first and
ABORTS (raises, no partial state, nothing added) if it finds any
violating row, rather than silently deleting or "fixing" data.

This preflight was run and passed against this session's available test/
dev PostgreSQL environment (see the M1.3 report for the exact evidence —
zero violations found there). It has NOT been run against any real
production database, since none was reachable from this session. That is
exactly why the check is embedded in the migration itself rather than
only run manually once: whenever this migration is actually applied to a
real environment (including production, on deploy), it re-validates
against that environment's actual data before touching the schema, and
fails loudly and safely if that data doesn't hold up — it does not trust
this session's clean result to still be true elsewhere.

Checks performed (Phase M1.3 §20):
  A. Duplicate (society_id, normalized vehicle_number) among active vehicles
  B. resident_id AND tenant_id both set on the same row
  (C: cross-society resident/tenant/flat references, and D: blank/invalid
  numbers, are checked and reported for visibility in the M1.3 report, but
  are not blocking preconditions for the two constraints below — C isn't
  something a CHECK/UNIQUE constraint can enforce at all, and D is already
  structurally prevented by vehicle_number being NOT NULL with no code
  path that can produce an empty string post-normalization.)
"""
from alembic import op
import sqlalchemy as sa

revision      = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    conn = op.get_bind()

    # A. Duplicate normalized vehicle_number within the same active society scope.
    #    Mirrors app/utils/vehicle_number.py's normalize_vehicle_number() exactly
    #    (upper, strip spaces and dashes) so the DB-level check matches what the
    #    application actually enforces.
    dupes = conn.execute(sa.text("""
        SELECT society_id,
               UPPER(REPLACE(REPLACE(vehicle_number, ' ', ''), '-', '')) AS normalized,
               COUNT(*) AS n
        FROM vehicles
        WHERE is_active = true
        GROUP BY society_id, normalized
        HAVING COUNT(*) > 1
    """)).fetchall()

    # B. resident_id AND tenant_id both set.
    xor_violations = conn.execute(sa.text("""
        SELECT id FROM vehicles
        WHERE resident_id IS NOT NULL AND tenant_id IS NOT NULL
    """)).fetchall()

    if dupes or xor_violations:
        lines = ["VEHICLE CONSTRAINT PREFLIGHT — BLOCKED"]
        if dupes:
            lines.append(f"  Duplicate normalized vehicle_number groups: {len(dupes)}")
            for society_id, normalized, n in dupes:
                lines.append(f"    society_id={society_id} normalized={normalized!r} count={n}")
        if xor_violations:
            ids = ", ".join(str(row[0]) for row in xor_violations)
            lines.append(f"  Rows with both resident_id and tenant_id set: {len(xor_violations)} ({ids})")
        lines.append("  Constraints NOT added. Resolve the rows above, then re-run this migration.")
        raise RuntimeError("\n".join(lines))

    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'vehicles'
                  AND constraint_name = 'ck_vehicle_resident_tenant_xor'
            ) THEN
                ALTER TABLE vehicles
                    ADD CONSTRAINT ck_vehicle_resident_tenant_xor
                    CHECK (resident_id IS NULL OR tenant_id IS NULL);
            END IF;
        END $$
    """))

    # Postgres UNIQUE constraints can't reference an expression directly the
    # way an index can — use a unique partial index on the normalized value,
    # same pattern already used for uq_resident_primary_per_flat.
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicle_society_normalized_number
        ON vehicles (society_id, UPPER(REPLACE(REPLACE(vehicle_number, ' ', ''), '-', '')))
        WHERE is_active = true
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_vehicle_society_normalized_number"))
    op.execute(sa.text("ALTER TABLE vehicles DROP CONSTRAINT IF EXISTS ck_vehicle_resident_tenant_xor"))
