"""Per-society service switches

Revision ID: e1b4c8d6f3a2
Revises: d9a3b7c5e2f1
Create Date: 2026-10-12

society_services: the platform owner's switch for one service of one society; a row with enabled = false means the
service is off. No rows means every society keeps every service, as today. Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'e1b4c8d6f3a2'
down_revision = 'd9a3b7c5e2f1'
branch_labels = None
depends_on    = None


def upgrade():
    if 'society_services' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'society_services',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_key', sa.String(40), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('society_id', 'service_key', name='uq_society_services_key'),
    )
    op.create_index('ix_society_services_society_id', 'society_services', ['society_id'])


def downgrade():
    op.drop_table('society_services')
