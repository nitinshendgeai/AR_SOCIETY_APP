"""Visitor gate pass code

Revision ID: 5e0f1a2b3c4d
Revises: 4d9e0f1a2b3c
Create Date: 2026-11-06

visitors.pass_code: the short code a guest invited by a resident reads out at the gate (the guard verifies it, then checks
the guest in). Cleared on check-in and check-out. Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = '5e0f1a2b3c4d'
down_revision = '4d9e0f1a2b3c'
branch_labels = None
depends_on    = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'pass_code' not in {c['name'] for c in insp.get_columns('visitors')}:
        op.add_column('visitors', sa.Column('pass_code', sa.String(length=8), nullable=True))
    if 'ix_visitors_pass_code' not in {i['name'] for i in insp.get_indexes('visitors')}:
        op.create_index('ix_visitors_pass_code', 'visitors', ['pass_code'])


def downgrade():
    op.drop_index('ix_visitors_pass_code', table_name='visitors')
    op.drop_column('visitors', 'pass_code')
