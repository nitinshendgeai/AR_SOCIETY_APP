"""Flat charges know their income head and where they came from

Revision ID: a9c3e5f7b1d2
Revises: f8a2c6e0b3d5
Create Date: 2026-10-25

flat_charges.charge_type: the income head an additional charge is booked to (amenities, parking...), unset for the
usual "other charges". flat_charges.source_type / source_id: what raised it (an amenity booking, a parking violation).
Additive and idempotent: every existing charge keeps no head and no source.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'a9c3e5f7b1d2'
down_revision = 'f8a2c6e0b3d5'
branch_labels = None
depends_on    = None


def _has(table, name):
    return name in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table, name):
    return name in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    if not _has('flat_charges', 'charge_type'):
        op.add_column('flat_charges', sa.Column('charge_type', postgresql.ENUM(name='chargetype', create_type=False),
                                                nullable=True))
    if not _has('flat_charges', 'source_type'):
        op.add_column('flat_charges', sa.Column('source_type', sa.String(length=40), nullable=True))
    if not _has('flat_charges', 'source_id'):
        op.add_column('flat_charges', sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True))
    if not _has_index('flat_charges', 'ix_flat_charges_source_type'):
        op.create_index('ix_flat_charges_source_type', 'flat_charges', ['source_type'])
    if not _has_index('flat_charges', 'ix_flat_charges_source_id'):
        op.create_index('ix_flat_charges_source_id', 'flat_charges', ['source_id'])


def downgrade():
    op.drop_index('ix_flat_charges_source_id', table_name='flat_charges')
    op.drop_index('ix_flat_charges_source_type', table_name='flat_charges')
    op.drop_column('flat_charges', 'source_id')
    op.drop_column('flat_charges', 'source_type')
    op.drop_column('flat_charges', 'charge_type')
