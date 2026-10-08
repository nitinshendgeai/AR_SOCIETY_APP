"""Merge the existing migration branches into a single Alembic head.

Revision ID: b3c4d5e6f7a9
Revises: a2b3c4d5e6f8, a1b2c3d4e5f6
Create Date: 2026-10-08

This is a graph-only merge. Both parent migrations are already part of the
schema history and have independent, non-conflicting DDL. No schema changes
are performed here.
"""
revision = "b3c4d5e6f7a9"
down_revision = ("a2b3c4d5e6f8", "a1b2c3d4e5f6")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
