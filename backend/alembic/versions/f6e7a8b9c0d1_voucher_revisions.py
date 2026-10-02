"""Accounts: editing vouchers

Revision ID: f6e7a8b9c0d1
Revises: f5e6f7a8b9c0
Create Date: 2026-10-02

A voucher the society entered can be corrected while its year is open. Adds
edited_at / edited_by on vouchers and voucher_revisions, which keeps each
earlier version (date, number, amount, narration and lines) with who changed
it, when and why. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'f6e7a8b9c0d1'
down_revision = 'f5e6f7a8b9c0'
branch_labels = None
depends_on    = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('vouchers')}
    if 'edited_at' not in columns:
        op.add_column('vouchers', sa.Column('edited_at', sa.DateTime(), nullable=True))
    if 'edited_by' not in columns:
        op.add_column('vouchers', sa.Column('edited_by', UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_vouchers_edited_by', 'vouchers', 'users',
                              ['edited_by'], ['id'], ondelete='SET NULL')

    if 'voucher_revisions' not in inspector.get_table_names():
        op.create_table(
            'voucher_revisions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('revision_no', sa.Integer(), nullable=False),
            sa.Column('snapshot', sa.JSON(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('edited_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_voucher_revisions_voucher_id', 'voucher_revisions', ['voucher_id'])


def downgrade():
    op.drop_table('voucher_revisions')
    op.drop_constraint('fk_vouchers_edited_by', 'vouchers', type_='foreignkey')
    op.drop_column('vouchers', 'edited_by')
    op.drop_column('vouchers', 'edited_at')
