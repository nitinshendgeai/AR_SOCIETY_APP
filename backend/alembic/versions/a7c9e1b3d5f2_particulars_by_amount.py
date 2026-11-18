"""Printed bills list their particulars by amount, largest first, for every society

Revision ID: a7c9e1b3d5f2
Revises: e3a5c7d9f1b4
Create Date: 2026-11-18

maintenance_settings.particulars_order now defaults to "amount" and every existing society is switched to it. Only how
a bill prints changes. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'a7c9e1b3d5f2'
down_revision = 'e3a5c7d9f1b4'
branch_labels = None
depends_on    = None


def upgrade():
    with op.batch_alter_table('maintenance_settings') as batch:
        batch.alter_column('particulars_order', existing_type=sa.String(length=20), existing_nullable=False,
                           server_default='amount')
    op.execute("UPDATE maintenance_settings SET particulars_order = 'amount' WHERE particulars_order <> 'amount'")


def downgrade():
    with op.batch_alter_table('maintenance_settings') as batch:
        batch.alter_column('particulars_order', existing_type=sa.String(length=20), existing_nullable=False,
                           server_default='elements')
