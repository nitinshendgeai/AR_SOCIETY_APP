"""Add the missing is_active column to two tables the models expect to have it.

`accounting_posting_errors` and `vendor_payment_transactions` were created by
migrations without the `is_active` column that every model inheriting
`TimestampMixin` carries. On a database built from the migrations the models'
SELECTs fail ("column ... is_active does not exist"): after each automatic
posting the "resolve any open error" lookup raised, the posting was recorded as
failed, and recording a payment answered 500.

Idempotent: a database that already has the column (one created from the
models) is left alone.

Revision ID: 9d6e7f8091a2
Revises: 8c5d6e7f8091
"""
from alembic import op
import sqlalchemy as sa

revision = "9d6e7f8091a2"
down_revision = "8c5d6e7f8091"
branch_labels = None
depends_on = None

TABLES = ("accounting_posting_errors", "vendor_payment_transactions")


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return True  # nothing to add to
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade():
    bind = op.get_bind()
    for table in TABLES:
        if not _has_column(bind, table, "is_active"):
            op.add_column(table, sa.Column("is_active", sa.Boolean(), nullable=False,
                                           server_default=sa.true()))


def downgrade():
    bind = op.get_bind()
    for table in TABLES:
        if _has_column(bind, table, "is_active"):
            op.drop_column(table, "is_active")
