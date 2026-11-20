"""Accounts Agent — administrative recovery of dead monitoring events

Revision ID: e5f7a9b1c3d5
Revises: d4e6f8a0b2c4
Create Date: 2026-11-20

Adds nullable columns to accounts_agent_events so an administrator can requeue a dead event (a limited number of
times) or acknowledge it with a note: dead_at, requeue_count, acknowledged_at, acknowledged_by, acknowledge_note.
No existing data changes. Idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'e5f7a9b1c3d5'
down_revision = 'd4e6f8a0b2c4'
branch_labels = None
depends_on    = None

TABLE = 'accounts_agent_events'
COLUMNS = [
    sa.Column('dead_at', sa.DateTime(), nullable=True),
    sa.Column('requeue_count', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
    sa.Column('acknowledged_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    sa.Column('acknowledge_note', sa.Text(), nullable=True),
]


def _existing():
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade():
    have = _existing()
    for col in COLUMNS:
        if col.name not in have:
            op.add_column(TABLE, col)


def downgrade():
    have = _existing()
    for col in reversed(COLUMNS):
        if col.name in have:
            op.drop_column(TABLE, col.name)
