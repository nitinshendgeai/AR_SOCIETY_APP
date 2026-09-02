"""wing_floor_soft_delete_unique_indexes

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-02

wings.uq_wing_society_name, wings.uq_wing_society_code, and
floors.uq_floor_wing_number were plain table-level UNIQUE constraints —
not scoped to is_active. Soft-deleting a wing/floor (is_active=False)
leaves the row in place, so re-creating a new one with the same
name/code/floor_number hit this hard constraint at the DB layer with a
raw IntegrityError (surfaced to the client as a generic 409 "Duplicate
entry"), even though the application-level assert_unique_name/
assert_unique_code/assert_unique_number checks in wing_repo.py and
floor_repo.py already only look at active rows and would have allowed
it. A deleted wing/floor's name was effectively permanently unusable.

Same fix already applied to Vehicle/Resident in
d5e6f7a8b9c0_vehicle_constraints_with_preflight.py: replace the plain
UNIQUE constraint with a partial UNIQUE index that only applies to
active rows, matching what the application actually enforces.

Preflight: since active-row uniqueness is already enforced by both the
old constraint and the app-level checks, there should be zero active
duplicates to find — this only guards against something having bypassed
those checks (a direct DB write, an old code path, etc.) before the new
partial index is created, since CREATE UNIQUE INDEX would otherwise
just fail with an opaque error if any existed.
"""
from alembic import op
import sqlalchemy as sa

revision      = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    conn = op.get_bind()

    wing_name_dupes = conn.execute(sa.text("""
        SELECT society_id, name, COUNT(*) AS n
        FROM wings
        WHERE is_active = true
        GROUP BY society_id, name
        HAVING COUNT(*) > 1
    """)).fetchall()

    wing_code_dupes = conn.execute(sa.text("""
        SELECT society_id, code, COUNT(*) AS n
        FROM wings
        WHERE is_active = true AND code IS NOT NULL
        GROUP BY society_id, code
        HAVING COUNT(*) > 1
    """)).fetchall()

    floor_dupes = conn.execute(sa.text("""
        SELECT wing_id, floor_number, COUNT(*) AS n
        FROM floors
        WHERE is_active = true
        GROUP BY wing_id, floor_number
        HAVING COUNT(*) > 1
    """)).fetchall()

    if wing_name_dupes or wing_code_dupes or floor_dupes:
        lines = ["WING/FLOOR UNIQUE-INDEX PREFLIGHT — BLOCKED"]
        if wing_name_dupes:
            lines.append(f"  Duplicate active (society_id, name) groups in wings: {len(wing_name_dupes)}")
            for society_id, name, n in wing_name_dupes:
                lines.append(f"    society_id={society_id} name={name!r} count={n}")
        if wing_code_dupes:
            lines.append(f"  Duplicate active (society_id, code) groups in wings: {len(wing_code_dupes)}")
            for society_id, code, n in wing_code_dupes:
                lines.append(f"    society_id={society_id} code={code!r} count={n}")
        if floor_dupes:
            lines.append(f"  Duplicate active (wing_id, floor_number) groups in floors: {len(floor_dupes)}")
            for wing_id, floor_number, n in floor_dupes:
                lines.append(f"    wing_id={wing_id} floor_number={floor_number} count={n}")
        lines.append("  Indexes NOT changed. Resolve the rows above, then re-run this migration.")
        raise RuntimeError("\n".join(lines))

    op.drop_constraint('uq_wing_society_code', 'wings', type_='unique')
    op.drop_constraint('uq_wing_society_name', 'wings', type_='unique')
    op.drop_constraint('uq_floor_wing_number', 'floors', type_='unique')

    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_wing_society_name
        ON wings (society_id, name)
        WHERE is_active = true
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_wing_society_code
        ON wings (society_id, code)
        WHERE is_active = true
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_floor_wing_number
        ON floors (wing_id, floor_number)
        WHERE is_active = true
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_wing_society_name"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_wing_society_code"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_floor_wing_number"))

    op.create_unique_constraint('uq_wing_society_name', 'wings', ['society_id', 'name'])
    op.create_unique_constraint('uq_wing_society_code', 'wings', ['society_id', 'code'])
    op.create_unique_constraint('uq_floor_wing_number', 'floors', ['wing_id', 'floor_number'])
