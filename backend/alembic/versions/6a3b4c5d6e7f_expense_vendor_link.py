"""Link expenses to the Vendor Master

Revision ID: 6a3b4c5d6e7f
Revises: 5f2a3b4c5d6e
Create Date: 2026-10-09

A payment voucher and a recurring expense can name the vendor that was paid, chosen from the Vendor
Master instead of typed. Existing recurring expenses whose free-text payee matches a vendor of the same
society by name are linked to it. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = '6a3b4c5d6e7f'
down_revision = '5f2a3b4c5d6e'
branch_labels = None
depends_on    = None


def _has_column(bind, table, column):
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    for table in ("vouchers", "recurring_expenses"):
        if not _has_column(bind, table, "vendor_id"):
            op.add_column(table, sa.Column("vendor_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
            op.create_foreign_key(f"fk_{table}_vendor_id", table, "vendors", ["vendor_id"], ["id"], ondelete="SET NULL")
            op.create_index(f"ix_{table}_vendor_id", table, ["vendor_id"])
    bind.execute(sa.text("""
        UPDATE recurring_expenses r SET vendor_id = v.id
        FROM vendors v
        WHERE r.vendor_id IS NULL AND r.payee IS NOT NULL
          AND v.society_id = r.society_id AND lower(trim(v.company_name)) = lower(trim(r.payee))
    """))


def downgrade():
    for table in ("recurring_expenses", "vouchers"):
        op.drop_index(f"ix_{table}_vendor_id", table_name=table)
        op.drop_constraint(f"fk_{table}_vendor_id", table, type_="foreignkey")
        op.drop_column(table, "vendor_id")
