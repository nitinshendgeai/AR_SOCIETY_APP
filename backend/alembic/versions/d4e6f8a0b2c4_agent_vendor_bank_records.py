"""Accounts Agent — history of vendor bank details (for the bank-account-change check)

Revision ID: d4e6f8a0b2c4
Revises: b8d0f2a4c6e1
Create Date: 2026-11-20

One new society-scoped table. Stores a fingerprint and a masked copy only (last four digits), never a full account
number. Nothing existing is altered. Idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'd4e6f8a0b2c4'
down_revision = 'b8d0f2a4c6e1'
branch_labels = None
depends_on    = None

TABLE = 'accounts_agent_vendor_bank_records'


def upgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('masked', sa.JSON(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('is_baseline', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('source', sa.String(20), nullable=False, server_default='scan'),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('vendor_id', 'fingerprint', 'first_seen_at', name='uq_agent_vendor_bank_record'),
        sa.Index('ix_agent_vendor_bank_vendor', 'vendor_id', 'first_seen_at'),
    )


def downgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
