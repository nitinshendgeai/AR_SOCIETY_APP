"""Add last_login to users table

Revision ID: f1g2h3i4j5k6
Revises: e2f3a4b5c6d7
Create Date: 2026-06-15

Changes:
- users.last_login (DateTime, nullable) — timestamp of most recent successful login
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1g2h3i4j5k6'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login")
