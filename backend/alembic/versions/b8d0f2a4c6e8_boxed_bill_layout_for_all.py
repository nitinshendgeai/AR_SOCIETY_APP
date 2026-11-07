"""Every society prints its maintenance bill in the Boxed layout

Revision ID: b8d0f2a4c6e8
Revises: 9b4c5d6e7f80
Create Date: 2026-11-07

maintenance_settings.bill_layout: switches every existing society to "boxed" and makes "boxed" the column default for new
societies. Standard and Classic remain available: a society can pick either again in its maintenance settings.

The layout is only how a bill prints; no bill, amount or due date is changed, and bills already made print in the new
layout the next time they are opened or downloaded.

Idempotent. The downgrade restores the old column default ("standard") but cannot know which layout each society used
before, so it leaves their current layout alone.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'b8d0f2a4c6e8'
down_revision = '9b4c5d6e7f80'
branch_labels = None
depends_on    = None


def _has(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has('maintenance_settings', 'bill_layout'):
        return
    with op.batch_alter_table('maintenance_settings') as batch:
        batch.alter_column('bill_layout', existing_type=sa.String(length=20), existing_nullable=False,
                           server_default='boxed')
    op.execute("UPDATE maintenance_settings SET bill_layout = 'boxed' WHERE bill_layout <> 'boxed'")


def downgrade():
    if _has('maintenance_settings', 'bill_layout'):
        with op.batch_alter_table('maintenance_settings') as batch:
            batch.alter_column('bill_layout', existing_type=sa.String(length=20), existing_nullable=False,
                               server_default='standard')
