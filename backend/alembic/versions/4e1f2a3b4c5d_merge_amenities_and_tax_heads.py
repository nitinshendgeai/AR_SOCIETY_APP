"""Merge the amenities form migration with the GST/TDS tax chain

Revision ID: 4e1f2a3b4c5d
Revises: 3d0e1f2a3b4c, f9b0c1d2e3f4
Create Date: 2026-10-08

Two branches grew in parallel (the notices/assets/amenities screens and the GST/TDS accounting work). No schema change.
"""
revision      = '4e1f2a3b4c5d'
down_revision = ('3d0e1f2a3b4c', 'f9b0c1d2e3f4')
branch_labels = None
depends_on    = None


def upgrade():
    pass


def downgrade():
    pass
