"""reset_unoccupied_flats

Revision ID: 0f5a6b7c8d9e
Revises: 0e4f5a6b7c8d
Create Date: 2026-10-30

Completes the one-time occupancy correction of 0e4f5a6b7c8d. That one set every flat with a resident or tenant on
record from the move-in rule and left flats with NOBODY on record as they were. This sets those to vacant too: a flat
is occupied only when someone has moved in, so a flat marked owner occupied or tenant occupied with no resident and no
tenant on record is vacant.

A flat marked tenant occupied (let out) loses its non-occupancy charge in billing once it is vacant, so each one reset
from tenant occupied is printed (wing and flat number) for anyone who needs to put the tenant on record, or restore it.
"""
from alembic import op
import sqlalchemy as sa

revision      = '0f5a6b7c8d9e'
down_revision = '0e4f5a6b7c8d'
branch_labels = None
depends_on    = None

_NO_OCCUPANTS = ("NOT EXISTS (SELECT 1 FROM tenants t WHERE t.flat_id = f.id) "
                 "AND NOT EXISTS (SELECT 1 FROM residents r WHERE r.flat_id = f.id)")


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"""
        SELECT f.id, f.flat_number, w.name, f.occupancy_status
          FROM flats f LEFT JOIN wings w ON w.id = f.wing_id
         WHERE f.occupancy_status IN ('owner_occupied', 'tenant_occupied') AND {_NO_OCCUPANTS}
         ORDER BY w.name, f.flat_number
    """)).fetchall()
    cast = "CAST(:s AS occupancystatus)" if bind.dialect.name == "postgresql" else ":s"
    update = sa.text(f"UPDATE flats SET occupancy_status = {cast} WHERE id = :id")
    let_out = []
    for flat_id, number, wing, status in rows:
        bind.execute(update, {"s": "vacant", "id": flat_id})
        if str(getattr(status, "value", status)) == "tenant_occupied":
            let_out.append(f"{wing or ''}-{number}")
    print(f"[migration] {len(rows)} flats with nobody on record set to vacant "
          f"({len(let_out)} of them were marked tenant occupied)")
    if let_out:
        print("[migration] were tenant occupied (no tenant on record): " + ", ".join(let_out[:200])
              + (f" … and {len(let_out) - 200} more" if len(let_out) > 200 else ""))


def downgrade() -> None:
    # The previous statuses are not kept (the let-out flats are printed above when this runs).
    pass
