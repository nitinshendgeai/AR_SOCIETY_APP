"""Depreciation setup: category rules and per-asset settings

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-11-16

depreciation_rules (how each asset category is depreciated) and asset_depreciation (an asset's own setting where it
differs). Only adds two tables; nothing existing is changed, and nothing is posted to the books.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'c3e5a7b9d1f3'
down_revision = 'b2d4f6a8c0e2'
branch_labels = None
depends_on    = None


def _base_columns():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if 'depreciation_rules' not in existing:
        op.create_table(
            'depreciation_rules', *_base_columns(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('asset_category', sa.String(30), nullable=False),
            sa.Column('method', sa.String(5), nullable=False, server_default='wdv'),
            sa.Column('rate', sa.Numeric(7, 4), nullable=False, server_default='0'),
            sa.Column('life_years', sa.Integer(), nullable=True),
            sa.Column('salvage_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
            sa.Column('ledger_system_key', sa.String(50), nullable=True),
            sa.Column('notes', sa.String(300), nullable=True),
            sa.UniqueConstraint('society_id', 'asset_category', name='uq_dep_rule_society_category'),
        )
        op.create_index('ix_depreciation_rules_society_id', 'depreciation_rules', ['society_id'])
    if 'asset_depreciation' not in existing:
        op.create_table(
            'asset_depreciation', *_base_columns(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('asset_id', UUID(as_uuid=True), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('depreciate', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('method', sa.String(5), nullable=True),
            sa.Column('rate', sa.Numeric(7, 4), nullable=True),
            sa.Column('life_years', sa.Integer(), nullable=True),
            sa.Column('salvage_value', sa.Numeric(14, 2), nullable=True),
            sa.Column('start_on', sa.Date(), nullable=True),
            sa.Column('stop_on', sa.Date(), nullable=True),
            sa.UniqueConstraint('asset_id', name='uq_asset_depreciation_asset'),
        )
        op.create_index('ix_asset_depreciation_society_id', 'asset_depreciation', ['society_id'])
        op.create_index('ix_asset_depreciation_asset_id', 'asset_depreciation', ['asset_id'])


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for t in ('asset_depreciation', 'depreciation_rules'):
        if t in existing:
            op.drop_table(t)
