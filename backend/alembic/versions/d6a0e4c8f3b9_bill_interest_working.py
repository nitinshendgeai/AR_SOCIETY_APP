"""Interest working on the maintenance bill

Revision ID: d6a0e4c8f3b9
Revises: c5f9d3b7e2a8
Create Date: 2026-10-24

maintenance_bills.interest_working: how the interest on the bill was worked out, per earlier bill (JSON text), so the
printed bill can show it. Additive and idempotent; bills made before this simply print no working.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'd6a0e4c8f3b9'
down_revision = 'c5f9d3b7e2a8'
branch_labels = None
depends_on    = None


def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('maintenance_bills')}
    if 'interest_working' not in cols:
        op.add_column('maintenance_bills', sa.Column('interest_working', sa.Text(), nullable=True))


def downgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('maintenance_bills')}
    if 'interest_working' in cols:
        op.drop_column('maintenance_bills', 'interest_working')
