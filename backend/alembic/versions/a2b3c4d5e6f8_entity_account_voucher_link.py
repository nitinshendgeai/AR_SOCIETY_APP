"""Link voucher entries to formal accounting subledgers.

Revision ID: a2b3c4d5e6f8
Revises: a1b2c3d4e5f7
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a2b3c4d5e6f8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("voucher_entries")}
    if "entity_account_id" not in columns:
        op.add_column("voucher_entries", sa.Column("entity_account_id", UUID(as_uuid=True),
                       sa.ForeignKey("entity_accounts.id", ondelete="SET NULL"), nullable=True))
        op.create_index("ix_voucher_entries_entity_account_id", "voucher_entries", ["entity_account_id"])

    # Account codes are identifiers within a society. Nullable custom accounts remain allowed.
    existing = {x["name"] for x in sa.inspect(op.get_bind()).get_indexes("accounts")}
    if "uq_accounts_society_code" not in existing:
        op.create_index("uq_accounts_society_code", "accounts", ["society_id", "code"], unique=True,
                        postgresql_where=sa.text("code IS NOT NULL"))


def downgrade():
    op.drop_index("uq_accounts_society_code", table_name="accounts")
    op.drop_index("ix_voucher_entries_entity_account_id", table_name="voucher_entries")
    op.drop_constraint("voucher_entries_entity_account_id_fkey", "voucher_entries", type_="foreignkey")
    op.drop_column("voucher_entries", "entity_account_id")
