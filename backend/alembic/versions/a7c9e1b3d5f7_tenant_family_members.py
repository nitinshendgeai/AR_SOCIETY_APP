"""Tenant family members

Revision ID: a7c9e1b3d5f7
Revises: e5f7a9b1c3d5
Create Date: 2026-11-22

A small table of the people who live with a tenant (name, relation, phone, date of birth), kept apart from residents.
Idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'a7c9e1b3d5f7'
down_revision = 'e5f7a9b1c3d5'
branch_labels = None
depends_on    = None

TABLE = 'tenant_family_members'


def upgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('relation', sa.String(50), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
    )
    op.create_index('ix_tenant_family_members_tenant_id', TABLE, ['tenant_id'])


def downgrade():
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
