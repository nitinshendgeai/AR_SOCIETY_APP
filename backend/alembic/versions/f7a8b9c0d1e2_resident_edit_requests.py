"""resident_edit_requests

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-03

Table: resident_edit_requests — Resident self-service profile change
requests, applied only on Admin/Committee approval.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    status_enum = sa.Enum('pending', 'approved', 'rejected', name='residenteditrequeststatus')

    op.create_table(
        'resident_edit_requests',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('resident_id',      UUID(as_uuid=True), nullable=False),
        sa.Column('requested_by',     UUID(as_uuid=True), nullable=True),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('changes',          sa.JSON(), nullable=False),
        sa.Column('status',           status_enum, nullable=False, server_default='pending'),
        sa.Column('reviewed_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at',      sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['resident_id'],  ['residents.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'],      ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['society_id'],   ['societies.id'],  ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'],  ['users.id'],      ondelete='SET NULL'),
    )
    op.create_index('ix_resident_edit_requests_id',          'resident_edit_requests', ['id'])
    op.create_index('ix_resident_edit_requests_resident_id', 'resident_edit_requests', ['resident_id'])
    op.create_index('ix_resident_edit_requests_requested_by','resident_edit_requests', ['requested_by'])
    op.create_index('ix_resident_edit_requests_society_id',  'resident_edit_requests', ['society_id'])
    op.create_index('ix_resident_edit_requests_status',      'resident_edit_requests', ['status'])


def downgrade() -> None:
    op.drop_table('resident_edit_requests')
    sa.Enum(name='residenteditrequeststatus').drop(op.get_bind(), checkfirst=True)
