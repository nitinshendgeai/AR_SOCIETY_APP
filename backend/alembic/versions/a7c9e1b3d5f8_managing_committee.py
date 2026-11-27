"""Managing committee register: the committee's term and its office-bearers with their powers and contacts

Revision ID: a7c9e1b3d5f8
Revises: f6b8d0e2a4c6
Create Date: 2026-11-27

Two new society-scoped tables; nothing existing is altered. Idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'a7c9e1b3d5f8'
down_revision = 'f6b8d0e2a4c6'
branch_labels = None
depends_on    = None


def _base():
    return [sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'),
                      nullable=False, index=True)]


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'managing_committees' not in tables:
        op.create_table(
            'managing_committees', *_base(),
            sa.Column('name', sa.String(150), nullable=False),
            sa.Column('formed_on', sa.Date(), nullable=False),
            sa.Column('term_ends_on', sa.Date(), nullable=True),
            sa.Column('election_note', sa.Text(), nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    if 'committee_members' not in tables:
        op.create_table(
            'committee_members', *_base(),
            sa.Column('committee_id', UUID(as_uuid=True), sa.ForeignKey('managing_committees.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('resident_id', UUID(as_uuid=True), sa.ForeignKey('residents.id', ondelete='SET NULL'), nullable=True),
            sa.Column('full_name', sa.String(255), nullable=False),
            sa.Column('flat_label', sa.String(60), nullable=True),
            sa.Column('position', sa.String(30), nullable=False, server_default='member'),
            sa.Column('phone', sa.String(20), nullable=True),
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('from_date', sa.Date(), nullable=False),
            sa.Column('to_date', sa.Date(), nullable=True),
            sa.Column('cheque_signatory', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('approves_payments', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('signs_documents', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('spending_limit', sa.Integer(), nullable=True),
            sa.Column('responsibilities', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='100'))


def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for t in ('committee_members', 'managing_committees'):
        if t in tables:
            op.drop_table(t)
