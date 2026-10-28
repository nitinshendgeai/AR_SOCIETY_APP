"""sync_flat_occupancy

Revision ID: 0e4f5a6b7c8d
Revises: 0d3e4f5a6b7c
Create Date: 2026-10-28

A flat's occupancy now follows who has moved in: tenant occupied when an active tenant has a move-in date, owner
occupied when an active resident has one, otherwise vacant (the possession date alone does not make a flat occupied).
This sets the stored status of existing flats from that rule, once.

Only flats that have at least one resident or tenant record are touched. A flat with no occupant record at all keeps
the status it was given, because nothing says it is wrong (a society may mark flats occupied, or let out, without
entering the people, and a let-out flat carries the non-occupancy charge in billing).
"""
from alembic import op
import sqlalchemy as sa

revision      = '0e4f5a6b7c8d'
down_revision = '0d3e4f5a6b7c'
branch_labels = None
depends_on    = None

_MOVED_IN = ("EXISTS (SELECT 1 FROM {table} o WHERE o.flat_id = f.id AND o.is_active = {true} "
             "AND o.move_out_date IS NULL AND o.move_in_date IS NOT NULL)")


def upgrade() -> None:
    bind = op.get_bind()
    true = "TRUE" if bind.dialect.name == "postgresql" else "1"
    rows = bind.execute(sa.text(f"""
        SELECT f.id, f.occupancy_status,
               {_MOVED_IN.format(table='tenants', true=true)}   AS tenant_in,
               {_MOVED_IN.format(table='residents', true=true)} AS resident_in
          FROM flats f
         WHERE EXISTS (SELECT 1 FROM tenants t WHERE t.flat_id = f.id)
            OR EXISTS (SELECT 1 FROM residents r WHERE r.flat_id = f.id)
    """)).fetchall()
    cast = "CAST(:s AS occupancystatus)" if bind.dialect.name == "postgresql" else ":s"
    update = sa.text(f"UPDATE flats SET occupancy_status = {cast} WHERE id = :id")
    changed = 0
    for flat_id, current, tenant_in, resident_in in rows:
        wanted = "tenant_occupied" if tenant_in else "owner_occupied" if resident_in else "vacant"
        if (current or "vacant") != wanted:
            bind.execute(update, {"s": wanted, "id": flat_id})
            changed += 1
    print(f"[migration] flat occupancy set from move-in dates on {changed} of {len(rows)} flats with occupants")


def downgrade() -> None:
    # The previous statuses are not kept; nothing to undo.
    pass
