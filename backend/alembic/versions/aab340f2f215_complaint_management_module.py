"""complaint_management_module

Revision ID: aab340f2f215
Revises: 20247a37e543
Create Date: 2026-05-23

Tables: complaints, complaint_comments, complaint_attachments, complaint_status_history
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = 'aab340f2f215'
down_revision = '20247a37e543'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    priority_enum  = sa.Enum('low','medium','high','critical',   name='complaintpriority')
    status_enum    = sa.Enum('open','assigned','in_progress','resolved','reopened','closed','rejected', name='complaintstatus')
    category_enum  = sa.Enum('plumbing','electrical','security','housekeeping','parking','lift','water','amenities','other', name='complaintcategory')

    # ── complaints ────────────────────────────────────────────────────────────
    op.create_table(
        'complaints',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('complaint_number', sa.String(20), nullable=False),
        sa.Column('title',            sa.String(255), nullable=False),
        sa.Column('description',      sa.Text(), nullable=False),
        sa.Column('category',         category_enum, nullable=False),
        sa.Column('priority',         priority_enum, nullable=False, server_default='medium'),
        sa.Column('status',           status_enum,   nullable=False, server_default='open'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',          UUID(as_uuid=True), nullable=True),
        sa.Column('raised_by',        UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_to',      UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_at',      sa.DateTime(), nullable=True),
        sa.Column('resolved_at',      sa.DateTime(), nullable=True),
        sa.Column('closed_at',        sa.DateTime(), nullable=True),
        sa.Column('due_date',         sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('reopen_count',     sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['raised_by'],   ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_complaints_id',              'complaints', ['id'])
    op.create_index('ix_complaints_complaint_number','complaints', ['complaint_number'], unique=True)
    op.create_index('ix_complaints_society_id',      'complaints', ['society_id'])
    op.create_index('ix_complaints_raised_by',       'complaints', ['raised_by'])
    op.create_index('ix_complaints_assigned_to',     'complaints', ['assigned_to'])
    op.create_index('ix_complaints_status',          'complaints', ['status'])
    op.create_index('ix_complaints_category',        'complaints', ['category'])
    op.create_index('ix_complaints_priority',        'complaints', ['priority'])

    # ── complaint_comments ────────────────────────────────────────────────────
    op.create_table(
        'complaint_comments',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('complaint_id', UUID(as_uuid=True), nullable=False),
        sa.Column('author_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('body',         sa.Text(), nullable=False),
        sa.Column('is_internal',  sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'],    ['users.id'],      ondelete='SET NULL'),
    )
    op.create_index('ix_complaint_comments_id',           'complaint_comments', ['id'])
    op.create_index('ix_complaint_comments_complaint_id', 'complaint_comments', ['complaint_id'])

    # ── complaint_attachments ─────────────────────────────────────────────────
    op.create_table(
        'complaint_attachments',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('complaint_id', UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_by',  UUID(as_uuid=True), nullable=True),
        sa.Column('file_name',    sa.String(255), nullable=False),
        sa.Column('file_url',     sa.String(500), nullable=False),
        sa.Column('file_size',    sa.Integer(), nullable=True),
        sa.Column('mime_type',    sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'],  ['users.id'],      ondelete='SET NULL'),
    )
    op.create_index('ix_complaint_attachments_id',           'complaint_attachments', ['id'])
    op.create_index('ix_complaint_attachments_complaint_id', 'complaint_attachments', ['complaint_id'])

    # ── complaint_status_history ──────────────────────────────────────────────
    op.create_table(
        'complaint_status_history',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('complaint_id', UUID(as_uuid=True), nullable=False),
        sa.Column('from_status',  status_enum, nullable=True),
        sa.Column('to_status',    status_enum, nullable=False),
        sa.Column('changed_by',   UUID(as_uuid=True), nullable=True),
        sa.Column('notes',        sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'],   ['users.id'],      ondelete='SET NULL'),
    )
    op.create_index('ix_complaint_status_history_id',           'complaint_status_history', ['id'])
    op.create_index('ix_complaint_status_history_complaint_id', 'complaint_status_history', ['complaint_id'])


def downgrade() -> None:
    op.drop_table('complaint_status_history')
    op.drop_table('complaint_attachments')
    op.drop_table('complaint_comments')
    op.drop_table('complaints')
    sa.Enum(name='complaintcategory').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='complaintstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='complaintpriority').drop(op.get_bind(), checkfirst=True)
