"""maintenance_settings: bank/UPI details and notes printed on bills

Revision ID: e8f9a0b1c2d3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-26
"""
from alembic import op

revision      = 'e8f9a0b1c2d3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on    = None

COLUMNS = [
    ("bank_account_name", "VARCHAR(150)"),
    ("bank_name", "VARCHAR(100)"),
    ("bank_account_number", "VARCHAR(40)"),
    ("bank_ifsc", "VARCHAR(20)"),
    ("upi_id", "VARCHAR(100)"),
    ("bill_notes", "TEXT"),
]


def upgrade():
    for name, sql_type in COLUMNS:
        op.execute(f'ALTER TABLE maintenance_settings ADD COLUMN IF NOT EXISTS "{name}" {sql_type}')


def downgrade():
    for name, _ in reversed(COLUMNS):
        op.execute(f'ALTER TABLE maintenance_settings DROP COLUMN IF EXISTS "{name}"')
