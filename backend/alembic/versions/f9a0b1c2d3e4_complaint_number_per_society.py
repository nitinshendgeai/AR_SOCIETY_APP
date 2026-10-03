"""Complaints: number unique per society, not across the platform

Revision ID: f9a0b1c2d3e4
Revises: f8f9a0b1c2d3
Create Date: 2026-10-03

Complaint numbers are CMP-00001, 00002 ... counted within each society, but the
unique index was on the number alone — so a second society's first complaint
collided with the first society's and failed. The index is now non-unique and
(society_id, complaint_number) is unique. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'f9a0b1c2d3e4'
down_revision = 'f8f9a0b1c2d3'
branch_labels = None
depends_on    = None

OLD = 'ix_complaints_complaint_number'
NEW = 'uq_complaint_society_number'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    indexes = {i['name']: i for i in inspector.get_indexes('complaints')}
    if OLD in indexes and indexes[OLD].get('unique'):
        op.drop_index(OLD, table_name='complaints')
        op.create_index(OLD, 'complaints', ['complaint_number'], unique=False)
    if NEW not in {i['name'] for i in inspector.get_indexes('complaints')} \
            and NEW not in {c['name'] for c in inspector.get_unique_constraints('complaints')}:
        op.create_unique_constraint(NEW, 'complaints', ['society_id', 'complaint_number'])


def downgrade():
    op.drop_constraint(NEW, 'complaints', type_='unique')
    op.drop_index(OLD, table_name='complaints')
    op.create_index(OLD, 'complaints', ['complaint_number'], unique=True)
