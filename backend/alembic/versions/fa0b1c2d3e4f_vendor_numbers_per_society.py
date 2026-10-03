"""Vendors: codes and numbers unique per society, not platform-wide

Revision ID: fa0b1c2d3e4f
Revises: f9a0b1c2d3e4
Create Date: 2026-10-03

Vendor codes (VND-0001), AMC contract numbers (AMC-2026-0001) and service request
numbers (SRQ-00001) are counted within each society, but their unique indexes were
on the number alone — so a second society's first vendor, contract or request
collided with the first society's and failed. Each index becomes non-unique and
(society_id, number) unique. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'fa0b1c2d3e4f'
down_revision = 'f9a0b1c2d3e4'
branch_labels = None
depends_on    = None

TABLES = [
    ('vendors',          'vendor_code',     'ix_vendors_vendor_code',                   'uq_vendor_society_code'),
    ('amc_contracts',    'contract_number', 'ix_amc_contracts_contract_number',         'uq_contract_society_number'),
    ('service_requests', 'request_number',  'ix_service_requests_request_number',       'uq_service_request_society_number'),
]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, col, index, unique in TABLES:
        indexes = {i['name']: i for i in inspector.get_indexes(table)}
        if index in indexes and indexes[index].get('unique'):
            op.drop_index(index, table_name=table)
            op.create_index(index, table, [col], unique=False)
        existing = {i['name'] for i in inspector.get_indexes(table)} | \
                   {c['name'] for c in inspector.get_unique_constraints(table)}
        if unique not in existing:
            op.create_unique_constraint(unique, table, ['society_id', col])


def downgrade():
    for table, col, index, unique in TABLES:
        op.drop_constraint(unique, table, type_='unique')
        op.drop_index(index, table_name=table)
        op.create_index(index, table, [col], unique=True)
