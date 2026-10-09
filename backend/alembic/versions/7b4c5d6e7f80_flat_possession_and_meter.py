"""Possession date and electricity meter on a flat

Revision ID: 7b4c5d6e7f80
Revises: 6a3b4c5d6e7f
Create Date: 2026-10-09

The day the owner took possession of the flat, and its electricity meter and consumer numbers. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = '7b4c5d6e7f80'
down_revision = '6a3b4c5d6e7f'
branch_labels = None
depends_on    = None

COLUMNS = (
    ("possession_date", sa.Date()),
    ("electric_meter_no", sa.String(40)),
    ("electric_consumer_no", sa.String(40)),
)


def upgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("flats")}
    for name, kind in COLUMNS:
        if name not in existing:
            op.add_column("flats", sa.Column(name, kind, nullable=True))


def downgrade():
    for name, _ in reversed(COLUMNS):
        op.drop_column("flats", name)
