"""online_payment_submissions.purpose

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-21

Adds `purpose` to online_payment_submissions — what the resident says a
recorded payment is for (maintenance, parking, sinking fund, ...), reusing
the existing ChargeType values. No bill is required to exist for this
record (see the table's original migration), so the receipt PDF prints
this directly as "on account of <purpose>" rather than deriving it from a
bill's line items. Defaults to 'maintenance', the overwhelming case, so
existing rows backfill cleanly.
"""
from alembic import op
import sqlalchemy as sa

revision      = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c['name'] for c in inspector.get_columns('online_payment_submissions')}

    if 'purpose' not in columns:
        op.add_column(
            'online_payment_submissions',
            sa.Column('purpose', sa.String(30), nullable=False, server_default='maintenance'),
        )


def downgrade() -> None:
    op.drop_column('online_payment_submissions', 'purpose')
