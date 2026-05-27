"""society_onboarding_handover_workflow

Revision ID: 259b1102d3cd
Revises: 5805225fd93e
Create Date: 2026-05-27

Changes:
  ALTER users: add must_change_password column
  CREATE: staff_handovers, handover_items
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '259b1102d3cd'
down_revision = '5805225fd93e'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── ALTER users: add must_change_password ─────────────────────────────────
    op.add_column('users',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='false')
    )

    # ── staff_handovers ───────────────────────────────────────────────────────
    handover_status_e = sa.Enum(
        'draft','submitted','accepted','disputed','verified','closed',
        name='handoverstatus'
    )
    op.create_table('staff_handovers',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',        sa.DateTime(), nullable=False),
        sa.Column('updated_at',        sa.DateTime(), nullable=False),
        sa.Column('is_active',         sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',        UUID(as_uuid=True), nullable=False),
        sa.Column('outgoing_staff_id', UUID(as_uuid=True), nullable=True),
        sa.Column('incoming_staff_id', UUID(as_uuid=True), nullable=True),
        sa.Column('duty_assignment_id',UUID(as_uuid=True), nullable=True),
        sa.Column('verified_by',       UUID(as_uuid=True), nullable=True),
        sa.Column('area',              sa.String(255), nullable=True),
        sa.Column('shift_start',       sa.DateTime(), nullable=True),
        sa.Column('shift_end',         sa.DateTime(), nullable=True),
        sa.Column('summary',           sa.Text(), nullable=False),
        sa.Column('status',            handover_status_e, nullable=False, server_default='draft'),
        sa.Column('accepted_at',       sa.DateTime(), nullable=True),
        sa.Column('acceptance_notes',  sa.Text(), nullable=True),
        sa.Column('dispute_reason',    sa.Text(), nullable=True),
        sa.Column('verified_at',       sa.DateTime(), nullable=True),
        sa.Column('verification_notes',sa.Text(), nullable=True),
        sa.Column('closed_at',         sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],        ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outgoing_staff_id'], ['staff.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incoming_staff_id'], ['staff.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verified_by'],       ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_staff_handovers_id',                'staff_handovers', ['id'])
    op.create_index('ix_staff_handovers_society_id',        'staff_handovers', ['society_id'])
    op.create_index('ix_staff_handovers_outgoing_staff_id', 'staff_handovers', ['outgoing_staff_id'])
    op.create_index('ix_staff_handovers_incoming_staff_id', 'staff_handovers', ['incoming_staff_id'])
    op.create_index('ix_staff_handovers_status',            'staff_handovers', ['status'])

    # ── handover_items ────────────────────────────────────────────────────────
    item_type_e = sa.Enum(
        'pending_task','incident','key','equipment','visitor','remark','maintenance',
        name='handoveritemtype'
    )
    op.create_table('handover_items',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('handover_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('item_type',    item_type_e, nullable=False),
        sa.Column('title',        sa.String(255), nullable=False),
        sa.Column('description',  sa.Text(), nullable=True),
        sa.Column('is_urgent',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_resolved',  sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reference_id', sa.String(100), nullable=True),
        sa.Column('quantity',     sa.Integer(), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ack_notes',    sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['handover_id'], ['staff_handovers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_handover_items_id',          'handover_items', ['id'])
    op.create_index('ix_handover_items_handover_id', 'handover_items', ['handover_id'])
    op.create_index('ix_handover_items_item_type',   'handover_items', ['item_type'])


def downgrade() -> None:
    op.drop_table('handover_items')
    op.drop_table('staff_handovers')
    sa.Enum(name='handoveritemtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='handoverstatus').drop(op.get_bind(), checkfirst=True)
    op.drop_column('users', 'must_change_password')
