"""password_reset_requests — "Forgot password?" requests handled by admins

Revision ID: e9f0a1b2c3d4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-26
"""
from alembic import op

revision      = 'e9f0a1b2c3d4'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE passwordresetstatus AS ENUM ('pending', 'completed', 'dismissed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id          UUID PRIMARY KEY,
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            society_id  UUID REFERENCES societies(id) ON DELETE CASCADE,
            identifier  VARCHAR(255) NOT NULL,
            status      passwordresetstatus NOT NULL,
            resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
            resolved_at TIMESTAMP,
            created_at  TIMESTAMP NOT NULL,
            updated_at  TIMESTAMP NOT NULL,
            is_active   BOOLEAN NOT NULL
        )
    """)
    for column in ("user_id", "society_id", "status", "resolved_by"):
        op.execute(f'CREATE INDEX IF NOT EXISTS "ix_password_reset_requests_{column}" '
                   f'ON password_reset_requests ({column})')


def downgrade():
    op.execute("DROP TABLE IF EXISTS password_reset_requests")
    op.execute("DROP TYPE IF EXISTS passwordresetstatus")
