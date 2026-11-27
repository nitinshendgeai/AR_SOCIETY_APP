"""Maintenance element: the ledger its bill lines are credited to

Revision ID: f6b8d0e2a4c6
Revises: e5a7c9d1f3b5
Create Date: 2026-11-27

maintenance_elements.credit_ledger_id (nullable, FK accounts.id ON DELETE SET NULL): set from the society's bye-laws or
accounting policy (by the committee, through the Accounts Agent's element review). NULL keeps the standard element
table, so existing societies post exactly as before. Additive, idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'f6b8d0e2a4c6'
down_revision = 'e5a7c9d1f3b5'
branch_labels = None
depends_on    = None

FK = 'fk_maintenance_elements_credit_ledger'


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'credit_ledger_id' not in {c['name'] for c in insp.get_columns('maintenance_elements')}:
        op.add_column('maintenance_elements', sa.Column('credit_ledger_id', UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(FK, 'maintenance_elements', 'accounts', ['credit_ledger_id'], ['id'], ondelete='SET NULL')


def downgrade():
    insp = sa.inspect(op.get_bind())
    if 'credit_ledger_id' in {c['name'] for c in insp.get_columns('maintenance_elements')}:
        if FK in {f.get('name') for f in insp.get_foreign_keys('maintenance_elements')}:
            op.drop_constraint(FK, 'maintenance_elements', type_='foreignkey')
        op.drop_column('maintenance_elements', 'credit_ledger_id')
