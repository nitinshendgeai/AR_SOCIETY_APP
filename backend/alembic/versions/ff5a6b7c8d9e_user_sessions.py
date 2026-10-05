"""Signed-in devices (user_sessions)

Revision ID: ff5a6b7c8d9e
Revises: fe4f5a6b7c8d
Create Date: 2026-10-05

One row per signed-in device. Tokens carry the row's id so a device can be signed out
(logout, "sign out other devices", password change or reset). Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'ff5a6b7c8d9e'
down_revision = 'fe4f5a6b7c8d'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    if 'user_sessions' not in sa.inspect(bind).get_table_names():
        op.create_table(
            'user_sessions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('device', sa.String(120), nullable=True),
            sa.Column('ip_address', sa.String(64), nullable=True),
            sa.Column('last_seen_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_reason', sa.String(40), nullable=True),
        )
    existing = {i['name'] for i in sa.inspect(bind).get_indexes('user_sessions')}
    for name, col in (('ix_user_sessions_user_id', 'user_id'), ('ix_user_sessions_revoked_at', 'revoked_at')):
        if name not in existing:
            op.create_index(name, 'user_sessions', [col])


def downgrade():
    bind = op.get_bind()
    if 'user_sessions' in sa.inspect(bind).get_table_names():
        for name in ('ix_user_sessions_revoked_at', 'ix_user_sessions_user_id'):
            op.drop_index(name, table_name='user_sessions')
        op.drop_table('user_sessions')
