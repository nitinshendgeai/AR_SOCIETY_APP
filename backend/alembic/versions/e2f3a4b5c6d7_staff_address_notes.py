"""Add address and notes fields to staff table

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-13

Changes:
- staff.address (Text, nullable) — staff residential address
- staff.notes (Text, nullable) — admin notes about the staff member
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("staff", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("staff", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("staff", "notes")
    op.drop_column("staff", "address")
