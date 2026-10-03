"""Structure: deactivated vs deleted wings, more flat types

Revision ID: f8f9a0b1c2d3
Revises: f7e8a9b0c1d2
Create Date: 2026-10-02

- wings.deleted_at: a deactivated wing (is_active false) can be switched on
  again; a deleted one cannot. Until now both were just is_active false, so
  a deactivated wing vanished for good. Wings already inactive are marked
  deleted (they were out of every list).
- flat types Duplex, Shop and Office, which the Add Flat form offers.

Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'f8f9a0b1c2d3'
down_revision = 'f7e8a9b0c1d2'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'deleted_at' not in {c['name'] for c in inspector.get_columns('wings')}:
        op.add_column('wings', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE wings SET deleted_at = updated_at WHERE is_active = false AND deleted_at IS NULL")

    if bind.dialect.name == 'postgresql':
        # ALTER TYPE ... ADD VALUE can't run inside a transaction on older servers
        with op.get_context().autocommit_block():
            for value in ('Duplex', 'Shop', 'Office'):
                op.execute(f"ALTER TYPE flattype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade():
    # Postgres can't drop enum values; flats of the new types would have to be
    # retyped first, so the types stay. Only the column goes.
    op.drop_column('wings', 'deleted_at')
