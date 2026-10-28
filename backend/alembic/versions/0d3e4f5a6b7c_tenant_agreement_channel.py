"""tenant_agreement_channel

Revision ID: 0d3e4f5a6b7c
Revises: 0c2d3e4f5a6b
Create Date: 2026-10-28

Which channel a tenant's agreement came through (direct, agent, online app, other) and the name of the agent or app.
Held on the tenant (the current terms) and on each agreement of the tenant's history. Plain text columns checked by the
API, not a database enum, so a new channel needs no migration.
"""
from alembic import op
import sqlalchemy as sa

revision      = '0d3e4f5a6b7c'
down_revision = '0c2d3e4f5a6b'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, channel, name in (("tenants", "agreement_channel", "agreement_channel_name"),
                                 ("agreement_tracker", "channel", "channel_name")):
        have = {c["name"] for c in inspector.get_columns(table)}
        if channel not in have:
            op.add_column(table, sa.Column(channel, sa.String(20), nullable=True))
        if name not in have:
            op.add_column(table, sa.Column(name, sa.String(150), nullable=True))


def downgrade() -> None:
    op.drop_column("agreement_tracker", "channel_name")
    op.drop_column("agreement_tracker", "channel")
    op.drop_column("tenants", "agreement_channel_name")
    op.drop_column("tenants", "agreement_channel")
