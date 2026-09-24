"""maintenance_calculation

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-24

Maintenance calculation engine:
- maintenance_charge_configs.basis (how a charge becomes a per-flat
  amount), is_service_charge, gst_applicable. Existing per-sq-ft charges
  are backfilled to basis=per_sqft; everything else becomes fixed, which
  is exactly how the generator already treated them.
- maintenance_bills.previous_dues / arrears_interest_upto for arrears
  display and interest-on-arrears tracking.
- maintenance_settings: one row per society of calculator rules.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on    = None

charge_basis = postgresql.ENUM(
    'fixed', 'per_sqft', 'construction_cost_pct', 'budget_equal', 'budget_area', 'parking',
    name='chargebasis',
)


def upgrade() -> None:
    charge_basis.create(op.get_bind(), checkfirst=True)
    op.add_column('maintenance_charge_configs',
                  sa.Column('basis', charge_basis, nullable=False, server_default='fixed'))
    op.add_column('maintenance_charge_configs',
                  sa.Column('is_service_charge', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('maintenance_charge_configs',
                  sa.Column('gst_applicable', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute("UPDATE maintenance_charge_configs SET basis = 'per_sqft' WHERE is_per_sqft = true")
    op.execute("UPDATE maintenance_charge_configs SET is_service_charge = true WHERE charge_type = 'maintenance'")

    op.add_column('maintenance_bills',
                  sa.Column('previous_dues', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('maintenance_bills', sa.Column('arrears_interest_upto', sa.Date(), nullable=True))

    op.create_table(
        'maintenance_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('society_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('construction_cost_per_sqft', sa.Numeric(10, 2), nullable=True),
        sa.Column('interest_rate_pct', sa.Numeric(5, 2), nullable=False, server_default='12'),
        sa.Column('interest_grace_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('non_occupancy_pct', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('gst_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('gst_rate_pct', sa.Numeric(5, 2), nullable=False, server_default='18'),
        sa.Column('gst_threshold_monthly', sa.Numeric(10, 2), nullable=False, server_default='7500'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index('ix_maintenance_settings_society_id', 'maintenance_settings', ['society_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_maintenance_settings_society_id', table_name='maintenance_settings')
    op.drop_table('maintenance_settings')
    op.drop_column('maintenance_bills', 'arrears_interest_upto')
    op.drop_column('maintenance_bills', 'previous_dues')
    op.drop_column('maintenance_charge_configs', 'gst_applicable')
    op.drop_column('maintenance_charge_configs', 'is_service_charge')
    op.drop_column('maintenance_charge_configs', 'basis')
    charge_basis.drop(op.get_bind(), checkfirst=True)
