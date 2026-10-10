"""Billing from the possession date: a society's billing start date and the period each bill charges for.

Revision ID: e4c1324d5e6f
Revises: d3b0213c4d5e
Create Date: 2026-10-10

Adds maintenance_settings.billing_start_date and maintenance_bills.period_start / period_end (all nullable; bills made
before this keep reading the cycle's own period). Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'e4c1324d5e6f'
down_revision = 'd3b0213c4d5e'
branch_labels = None
depends_on    = None


def _have(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if "billing_start_date" not in _have(bind, "maintenance_settings"):
        op.add_column("maintenance_settings", sa.Column("billing_start_date", sa.Date(), nullable=True))
    have = _have(bind, "maintenance_bills")
    if "period_start" not in have:
        op.add_column("maintenance_bills", sa.Column("period_start", sa.Date(), nullable=True))
    if "period_end" not in have:
        op.add_column("maintenance_bills", sa.Column("period_end", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("maintenance_bills", "period_end")
    op.drop_column("maintenance_bills", "period_start")
    op.drop_column("maintenance_settings", "billing_start_date")
