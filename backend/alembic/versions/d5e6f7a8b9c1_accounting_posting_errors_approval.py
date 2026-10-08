"""Accounting posting exception queue and manual voucher approval.

Revision ID: d5e6f7a8b9c1
Revises: c4d5e6f7a8b0
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "d5e6f7a8b9c1"
down_revision = "c4d5e6f7a8b0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vouchers", sa.Column("approval_status", sa.String(20), nullable=False, server_default="approved"))
    op.add_column("vouchers", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    op.add_column("vouchers", sa.Column("submitted_by", UUID(as_uuid=True),
                                         sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("vouchers", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("vouchers", sa.Column("approved_by", UUID(as_uuid=True),
                                         sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("vouchers", sa.Column("approval_note", sa.Text(), nullable=True))
    op.create_index("ix_vouchers_approval_status", "vouchers", ["approval_status"])

    op.create_table(
        "accounting_posting_errors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("society_id", UUID(as_uuid=True),
                  sa.ForeignKey("societies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("first_failed_at", sa.DateTime(), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("last_voucher_id", UUID(as_uuid=True),
                  sa.ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("society_id", "source_type", "source_id", "operation",
                            name="uq_accounting_posting_error_source"),
    )
    op.create_index("ix_accounting_posting_errors_society_id", "accounting_posting_errors", ["society_id"])
    op.create_index("ix_accounting_posting_errors_source_type", "accounting_posting_errors", ["source_type"])
    op.create_index("ix_accounting_posting_errors_source_id", "accounting_posting_errors", ["source_id"])
    op.create_index("ix_accounting_posting_errors_status", "accounting_posting_errors", ["status"])


def downgrade():
    op.drop_table("accounting_posting_errors")
    op.drop_index("ix_vouchers_approval_status", table_name="vouchers")
    for name in ("approval_note", "approved_by", "approved_at", "submitted_by", "submitted_at", "approval_status"):
        op.drop_column("vouchers", name)
