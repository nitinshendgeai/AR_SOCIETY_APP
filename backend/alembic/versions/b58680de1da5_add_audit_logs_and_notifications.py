"""add_audit_logs_and_notifications

Revision ID: b58680de1da5
Revises: 95390f45bba6
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision      = 'b58680de1da5'
down_revision = '95390f45bba6'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── audit_logs ────────────────────────────────────────────────────────────
    audit_action_enum = sa.Enum(
        'CREATE','UPDATE','DELETE','LOGIN','LOGOUT','ACCESS','APPROVE','REJECT','EXPORT',
        name='auditaction'
    )
    op.create_table(
        'audit_logs',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('user_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('user_email',  sa.String(255), nullable=True),
        sa.Column('action',      audit_action_enum, nullable=False),
        sa.Column('module',      sa.String(100), nullable=False),
        sa.Column('entity_id',   sa.String(100), nullable=True),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('old_values',  JSONB, nullable=True),
        sa.Column('new_values',  JSONB, nullable=True),
        sa.Column('ip_address',  sa.String(50), nullable=True),
        sa.Column('user_agent',  sa.String(500), nullable=True),
        sa.Column('notes',       sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_audit_logs_id',        'audit_logs', ['id'])
    op.create_index('ix_audit_logs_user_id',   'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action',    'audit_logs', ['action'])
    op.create_index('ix_audit_logs_module',    'audit_logs', ['module'])
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'])

    # ── notifications ─────────────────────────────────────────────────────────
    notif_channel_enum = sa.Enum('in_app','email','sms','push', name='notificationchannel')
    notif_status_enum  = sa.Enum('pending','sent','failed','read', name='notificationstatus')
    notif_type_enum    = sa.Enum('info','warning','alert','approval','reminder', name='notificationtype')

    op.create_table(
        'notifications',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('user_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('title',      sa.String(255), nullable=False),
        sa.Column('body',       sa.Text(), nullable=False),
        sa.Column('type',       notif_type_enum, nullable=False, server_default='info'),
        sa.Column('channel',    notif_channel_enum, nullable=False, server_default='in_app'),
        sa.Column('status',     notif_status_enum, nullable=False, server_default='pending'),
        sa.Column('is_read',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('module',     sa.String(100), nullable=True),
        sa.Column('entity_id',  sa.String(100), nullable=True),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('extra_data',   JSONB, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_notifications_id',      'notifications', ['id'])
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_status',  'notifications', ['status'])


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('audit_logs')
    sa.Enum(name='notificationtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='notificationstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='notificationchannel').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='auditaction').drop(op.get_bind(), checkfirst=True)
