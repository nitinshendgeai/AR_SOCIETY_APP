"""service_charge_pct_basis

Revision ID: 0c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
Create Date: 2026-10-26

A new way to work out a charge head: a percentage of the flat's own service-charge lines on the bill (the repair
and sinking funds as 0.75% / 0.25% of the monthly maintenance). Adds the value to the chargebasis enum, which both
maintenance_charge_configs.basis and maintenance_elements.default_basis use.
"""
from alembic import op

revision      = '0c2d3e4f5a6b'
down_revision = '0b1c2d3e4f5a'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # ALTER TYPE ... ADD VALUE can't run inside a transaction on older servers
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE chargebasis ADD VALUE IF NOT EXISTS 'service_charge_pct'")


def downgrade() -> None:
    # Postgres can't drop an enum value. Heads using it would have to be changed first, so the value stays.
    pass
