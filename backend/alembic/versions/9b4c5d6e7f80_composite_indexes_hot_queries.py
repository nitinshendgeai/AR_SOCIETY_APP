"""Composite indexes for the hot dashboard / billing / defaulters queries

Revision ID: 9b4c5d6e7f80
Revises: 8b3c4d5e6f7a
Create Date: 2026-11-07

Almost every list and counter in the app filters by society first and then by a status, a date or a flat, but the
tables only had single-column indexes, so Postgres picked one column and filtered the rest. These indexes match the
real filters (billing_repo, defaulters, dashboard_service). Small "pending" counters use partial indexes so only the
rows still waiting are indexed.

Safe on a live database and safe to re-run:
  - CREATE INDEX CONCURRENTLY does not lock writes, so it runs outside a transaction (autocommit_block).
  - IF NOT EXISTS skips indexes that are already there.
  - An index left INVALID by an earlier interrupted CONCURRENTLY build is dropped first, then built again.
The existing single-column indexes are left in place; drop them in a later migration once pg_stat_user_indexes
shows they are unused.
"""
from alembic import op
import sqlalchemy as sa

revision      = '9b4c5d6e7f80'
down_revision = '8b3c4d5e6f7a'
branch_labels = None
depends_on    = None

# (index name, table, column list incl. ordering, optional partial-index predicate)
INDEXES = [
    # --- Priority 1: billing, defaulters ---
    ("ix_bills_soc_status_due",        "maintenance_bills",          "society_id, bill_status, due_date",        "is_active"),
    ("ix_bills_flat_billdate",         "maintenance_bills",          "flat_id, bill_date DESC",                  "is_active"),
    ("ix_receipts_soc_flat_paydate",   "payment_receipts",           "society_id, flat_id, payment_date DESC",   None),
    ("ix_onlinepay_soc_flat_status",   "online_payment_submissions", "society_id, flat_id, status",              None),
    ("ix_notif_module_entity_created", "notifications",              "module, entity_id, created_at DESC",       None),
    # --- Priority 2: dashboard counters and lists ---
    ("ix_complaints_soc_status_created", "complaints",               "society_id, status, created_at",           None),
    ("ix_visitors_soc_status",         "visitors",                   "society_id, status",                       None),
    ("ix_visitors_soc_created",        "visitors",                   "society_id, created_at DESC",              None),
    ("ix_amenity_bookings_soc_pending", "amenity_bookings",          "society_id",                               "status = 'pending'"),
    ("ix_staff_leaves_soc_pending",    "staff_leaves",               "society_id",                               "status = 'pending' AND is_active"),
    ("ix_staff_attendance_soc_unapproved", "staff_attendance",       "society_id",                               "is_approved = false AND is_active"),
    ("ix_staff_attendance_staff_date", "staff_attendance",           "staff_id, attendance_date",                None),
    ("ix_vendor_invoices_soc_unpaid_due", "vendor_invoices",         "society_id, due_date",                     "is_paid = false AND is_active"),
    ("ix_agreements_soc_status_end",   "agreement_tracker",          "society_id, status, end_date",             None),
    ("ix_resident_edit_req_soc_status", "resident_edit_requests",    "society_id, status",                       None),
    ("ix_password_reset_soc_status",   "password_reset_requests",    "society_id, status",                       None),
]


def _drop_invalid(bind, names):
    rows = bind.execute(sa.text(
        "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "WHERE NOT i.indisvalid AND c.relname = ANY(:names)"), {"names": list(names)}).fetchall()
    for (name,) in rows:
        op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    todo = [i for i in INDEXES if i[1] in tables]
    with op.get_context().autocommit_block():
        _drop_invalid(bind, [i[0] for i in todo])
        for name, table, cols, where in todo:
            sql = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{name}" ON {table} ({cols})'
            if where:
                sql += f" WHERE {where}"
            op.execute(sql)


def downgrade():
    with op.get_context().autocommit_block():
        for name, *_ in reversed(INDEXES):
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')
