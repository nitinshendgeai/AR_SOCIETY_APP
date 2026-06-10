"""add society_id to users

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-06-10

Adds a nullable society_id FK on the users table so that /auth/me can
return the user's society without an extra query.  Platform Admin users
(is_superadmin=True) have no society, so the column is nullable.

Existing rows are left NULL — they will be populated when users log in
and are re-associated via the onboarding flow.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = 'a1b2c3d4e5f6'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'society_id',
            UUID(as_uuid=True),
            sa.ForeignKey('societies.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_users_society_id', 'users', ['society_id'])


def downgrade() -> None:
    op.drop_index('ix_users_society_id', table_name='users')
    op.drop_column('users', 'society_id')
