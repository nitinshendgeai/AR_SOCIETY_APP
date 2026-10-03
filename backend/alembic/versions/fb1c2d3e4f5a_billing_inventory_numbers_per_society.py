"""Billing and inventory: numbers unique per society, not platform-wide

Revision ID: fb1c2d3e4f5a
Revises: fa0b1c2d3e4f
Create Date: 2026-10-03

Maintenance bill numbers (INV-2026-00001), receipt numbers (RCP-/OPS-) and
inventory item / asset codes (INV-00001, AST-0001) are counted within each
society, but were unique across the whole platform — so a second society's first
bill, receipt, item or asset collided with the first society's and failed. Any
unique index or constraint on the number alone is replaced by a plain index, and
(society_id, number) becomes unique. Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = 'fb1c2d3e4f5a'
down_revision = 'fa0b1c2d3e4f'
branch_labels = None
depends_on    = None

TARGETS = [
    ('maintenance_bills',          'invoice_number', 'uq_bill_society_invoice_number'),
    ('payment_receipts',           'receipt_number', 'uq_receipt_society_number'),
    ('online_payment_submissions', 'receipt_number', 'uq_online_payment_society_receipt'),
    ('inventory_items',            'item_code',      'uq_item_society_code'),
    ('assets',                     'asset_code',     'uq_asset_society_code'),
]


def upgrade():
    bind = op.get_bind()
    for table, col, unique in TARGETS:
        inspector = sa.inspect(bind)
        # A unique constraint on the number alone (its backing index goes with it)
        for uc in inspector.get_unique_constraints(table):
            if uc['column_names'] == [col]:
                op.drop_constraint(uc['name'], table, type_='unique')
        inspector = sa.inspect(bind)
        # ... and any plain unique index on it, kept as a non-unique one
        for ix in inspector.get_indexes(table):
            if ix.get('unique') and ix['column_names'] == [col]:
                op.drop_index(ix['name'], table_name=table)
                op.create_index(ix['name'], table, [col], unique=False)
        inspector = sa.inspect(bind)
        if not any(ix['column_names'] == [col] for ix in inspector.get_indexes(table)):
            op.create_index(f'ix_{table}_{col}', table, [col], unique=False)
        existing = {i['name'] for i in inspector.get_indexes(table)} | \
                   {c['name'] for c in inspector.get_unique_constraints(table)}
        if unique not in existing:
            op.create_unique_constraint(unique, table, ['society_id', col])


def downgrade():
    for table, col, unique in TARGETS:
        op.drop_constraint(unique, table, type_='unique')
        op.create_unique_constraint(f'uq_{table}_{col}', table, [col])
