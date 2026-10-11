"""Interest waivers: no interest, or a lower rate, on one flat's arrears

Revision ID: d9a3b7c5e2f1
Revises: c8f2a6d4b1e9
Create Date: 2026-10-11

interest_waivers: a concession given by the committee, with a reason, for a date range. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'd9a3b7c5e2f1'
down_revision = 'c8f2a6d4b1e9'
branch_labels = None
depends_on    = None


def upgrade():
    if 'interest_waivers' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'interest_waivers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cancelled_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('mode', sa.String(10), nullable=False, server_default='waive'),
        sa.Column('rate_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(10), nullable=False, server_default='active'),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancel_reason', sa.Text(), nullable=True),
    )
    for col in ('society_id', 'flat_id', 'created_by', 'cancelled_by', 'status'):
        op.create_index(f'ix_interest_waivers_{col}', 'interest_waivers', [col])


def downgrade():
    op.drop_table('interest_waivers')
