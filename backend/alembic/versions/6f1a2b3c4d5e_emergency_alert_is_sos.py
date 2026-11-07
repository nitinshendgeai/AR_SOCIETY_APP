"""Emergency alert: a resident's SOS

Revision ID: 6f1a2b3c4d5e
Revises: 5e0f1a2b3c4d
Create Date: 2026-11-06

emergency_alerts.is_sos: set on an alert a resident raised with the SOS button. Such an alert is shown to security, the
committee and the resident who raised it, not to every resident. Additive and idempotent; existing alerts are not SOS.
"""
import sqlalchemy as sa
from alembic import op

revision      = '6f1a2b3c4d5e'
down_revision = '5e0f1a2b3c4d'
branch_labels = None
depends_on    = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'is_sos' not in {c['name'] for c in insp.get_columns('emergency_alerts')}:
        op.add_column('emergency_alerts', sa.Column('is_sos', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('emergency_alerts', 'is_sos')
