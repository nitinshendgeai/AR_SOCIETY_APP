"""Requests to add a family member, approved by the office

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5b7d9f1
Create Date: 2026-11-15

resident_family_requests: a resident (an owner or co-owner) asks to add a family member or dependent to their flat. Nothing
reaches the Residents list until the Admin or a committee member approves. Only adds a table; nothing existing is changed.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'b2d4f6a8c0e2'
down_revision = 'a1c3e5b7d9f1'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    if 'resident_family_requests' in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        'resident_family_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requester_name', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('resident_type', sa.String(20), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('status', sa.String(10), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('resident_id', UUID(as_uuid=True), sa.ForeignKey('residents.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_resident_family_requests_society_id', 'resident_family_requests', ['society_id'])
    op.create_index('ix_resident_family_requests_flat_id', 'resident_family_requests', ['flat_id'])
    op.create_index('ix_resident_family_requests_requested_by', 'resident_family_requests', ['requested_by'])
    op.create_index('ix_resident_family_requests_status', 'resident_family_requests', ['status'])
    op.create_index('ix_family_requests_soc_status', 'resident_family_requests', ['society_id', 'status'])


def downgrade():
    if 'resident_family_requests' in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table('resident_family_requests')
