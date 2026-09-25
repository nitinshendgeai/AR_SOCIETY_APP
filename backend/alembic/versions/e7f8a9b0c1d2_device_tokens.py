"""device_tokens — browsers and phones registered for push notifications

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-25
"""
from alembic import op

revision      = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on    = None


def upgrade():
    # IF NOT EXISTS throughout, like the other migrations, so a database that
    # already has the table (created outside migrations) still upgrades.
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_tokens (
            id           UUID PRIMARY KEY,
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token        VARCHAR(512) NOT NULL,
            platform     VARCHAR(20) NOT NULL,
            last_seen_at TIMESTAMP,
            created_at   TIMESTAMP NOT NULL,
            updated_at   TIMESTAMP NOT NULL,
            is_active    BOOLEAN NOT NULL
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS "ix_device_tokens_user_id" ON device_tokens (user_id)')
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS "ix_device_tokens_token" ON device_tokens (token)')


def downgrade():
    op.execute("DROP TABLE IF EXISTS device_tokens")
