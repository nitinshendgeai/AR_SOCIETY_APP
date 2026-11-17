"""Every society prints its maintenance bill in the Standard layout again

Revision ID: c9e1a3b5d7f9
Revises: d5a7c9e1b3f5
Create Date: 2026-11-17

maintenance_settings.bill_layout: sets every existing society back to "standard" (the original layout: grey letterhead
band, Head / Amount table, Notes box) and makes "standard" the column default for new societies again. Boxed and
Classic remain available: a society can pick either in its maintenance settings.

The layout is only how a bill prints; no bill, amount or due date is changed, and bills already made print in the
layout the next time they are opened or downloaded.

Idempotent. The downgrade restores the column default "boxed" but cannot know which layout each society used before,
so it leaves their current layout alone.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'c9e1a3b5d7f9'
down_revision = 'd5a7c9e1b3f5'
branch_labels = None
depends_on    = None


def _has(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if not _has('maintenance_settings', 'bill_layout'):
        return
    with op.batch_alter_table('maintenance_settings') as batch:
        batch.alter_column('bill_layout', existing_type=sa.String(length=20), existing_nullable=False,
                           server_default='standard')
    op.execute("UPDATE maintenance_settings SET bill_layout = 'standard' WHERE bill_layout <> 'standard'")


def downgrade():
    if _has('maintenance_settings', 'bill_layout'):
        with op.batch_alter_table('maintenance_settings') as batch:
            batch.alter_column('bill_layout', existing_type=sa.String(length=20), existing_nullable=False,
                               server_default='boxed')
