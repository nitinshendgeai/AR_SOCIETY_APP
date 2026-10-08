"""Vendor payment transaction identity.

Revision ID: c4d5e6f7a8b0
Revises: b3c4d5e6f7a9
Create Date: 2026-10-08

Adds transaction-level AP payment history without removing the invoice-level
paid_amount aggregate.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c4d5e6f7a8b0"
down_revision = "b3c4d5e6f7a9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vendor_payment_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("society_id", UUID(as_uuid=True),
                  sa.ForeignKey("societies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", UUID(as_uuid=True),
                  sa.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("vendor_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_number", sa.String(40), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_mode", sa.String(30), nullable=False),
        sa.Column("transaction_ref", sa.String(100), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_reversed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_vendor_payment_amount_positive"),
        sa.UniqueConstraint("society_id", "payment_number",
                            name="uq_vendor_payment_society_number"),
    )
    op.create_index("ix_vendor_payment_transactions_society_id",
                    "vendor_payment_transactions", ["society_id"])
    op.create_index("ix_vendor_payment_transactions_vendor_id",
                    "vendor_payment_transactions", ["vendor_id"])
    op.create_index("ix_vendor_payment_transactions_invoice_id",
                    "vendor_payment_transactions", ["invoice_id"])
    op.create_index("ix_vendor_payment_transactions_payment_date",
                    "vendor_payment_transactions", ["payment_date"])
    op.create_index("ix_vendor_payment_transactions_payment_mode",
                    "vendor_payment_transactions", ["payment_mode"])
    op.create_index("ix_vendor_payment_transactions_transaction_ref",
                    "vendor_payment_transactions", ["transaction_ref"])
    op.create_index("ix_vendor_payment_transactions_is_reversed",
                    "vendor_payment_transactions", ["is_reversed"])


def downgrade():
    op.drop_table("vendor_payment_transactions")
