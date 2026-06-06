"""enforce_society_isolation_users

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-06

Security fix: add society_id to users table and backfill from email pattern.

Every user created during onboarding has email {role}@{society_code}.com.
We match that pattern to set society_id.  Superadmin / platform-admin
accounts that don't match any society remain with society_id = NULL (correct).
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Add society_id column ──────────────────────────────────────────────
    op.execute(sa.text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS society_id UUID
            REFERENCES societies(id) ON DELETE CASCADE
    """))

    # ── 2. Index ──────────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_users_society_id ON users (society_id)
    """))

    # ── 3. Backfill onboarding users by email pattern {*}@{code}.com ─────────
    # Matches users whose email domain exactly equals a known society_code (lower).
    op.execute(sa.text("""
        UPDATE users u
        SET society_id = s.id
        FROM societies s
        WHERE u.society_id IS NULL
          AND u.is_active = true
          AND LOWER(u.email) LIKE '%@' || LOWER(s.society_code) || '.com'
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_society_id"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS society_id"))
