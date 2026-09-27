"""flats: virtual account number (VAN) printed on the bill

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-09-27
"""
from alembic import op

revision      = 'f0a1b2c3d4e5'
down_revision = 'e9f0a1b2c3d4'
branch_labels = None
depends_on    = None


def upgrade():
    op.execute('ALTER TABLE flats ADD COLUMN IF NOT EXISTS "virtual_account_number" VARCHAR(40)')


def downgrade():
    op.execute('ALTER TABLE flats DROP COLUMN IF EXISTS "virtual_account_number"')
