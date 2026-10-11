"""Two-wheeler rate on a parking charge head

Revision ID: c8f2a6d4b1e9
Revises: b7e3d1c9a4f2
Create Date: 2026-10-11

Adds maintenance_charge_configs.two_wheeler_rate (nullable): what a slot held for a two-wheeler pays a month, where it
differs from a car's. Empty keeps today's behaviour (one rate for every slot). Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'c8f2a6d4b1e9'
down_revision = 'b7e3d1c9a4f2'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("maintenance_charge_configs")}
    if "two_wheeler_rate" not in cols:
        op.add_column("maintenance_charge_configs", sa.Column("two_wheeler_rate", sa.Numeric(10, 2), nullable=True))


def downgrade():
    op.drop_column("maintenance_charge_configs", "two_wheeler_rate")
