"""Billing: payments set off against bills

Revision ID: f7e8a9b0c1d2
Revises: f6e7a8b9c0d1
Create Date: 2026-10-02

Adds payment_allocations: how much of a recorded payment settled which
maintenance bill. Payments are now set off against the flat's open bills,
oldest first, and an advance against the next bill issued.

Payments recorded against a bill before this (online_payment_submissions
.bill_id) were already applied to it in full; each gets its allocation row
so the record matches. Payments recorded "on account" are left as they are —
the Payments screen offers to set them off against the open bills. Also widens
due_trackers.advance_balance (10,2 → 14,2, like the other balances) so a large
advance can't overflow it. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'f7e8a9b0c1d2'
down_revision = 'f6e7a8b9c0d1'
branch_labels = None
depends_on    = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'payment_allocations' not in inspector.get_table_names():
        op.create_table(
            'payment_allocations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='SET NULL'), nullable=True),
            sa.Column('payment_id', UUID(as_uuid=True),
                      sa.ForeignKey('online_payment_submissions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('bill_id', UUID(as_uuid=True), sa.ForeignKey('maintenance_bills.id', ondelete='CASCADE'), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('allocated_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('released_at', sa.DateTime(), nullable=True),
            sa.Column('released_reason', sa.Text(), nullable=True),
        )
        for col in ('society_id', 'flat_id', 'payment_id', 'bill_id'):
            op.create_index(f'ix_payment_allocations_{col}', 'payment_allocations', [col])

    op.alter_column('due_trackers', 'advance_balance', existing_type=sa.Numeric(10, 2),
                    type_=sa.Numeric(14, 2), existing_nullable=False)

    # Payments already applied to their bill in full
    bind = op.get_bind()
    rows = bind.execute(sa.text("""
        SELECT s.id, s.created_at, s.society_id, s.flat_id, s.bill_id, s.amount, s.recorded_by
        FROM online_payment_submissions s
        WHERE s.bill_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM payment_allocations a WHERE a.payment_id = s.id)
    """)).fetchall()
    for r in rows:
        bind.execute(sa.text("""
            INSERT INTO payment_allocations
                (id, created_at, updated_at, is_active, society_id, flat_id, payment_id, bill_id, amount,
                 allocated_by)
            VALUES (:id, :at, :at, true, :society_id, :flat_id, :payment_id, :bill_id, :amount, :by)
        """), {"id": uuid.uuid4(), "at": r.created_at or datetime.utcnow(), "society_id": r.society_id,
               "flat_id": r.flat_id, "payment_id": r.id, "bill_id": r.bill_id, "amount": r.amount,
               "by": r.recorded_by})


def downgrade():
    op.drop_table('payment_allocations')
    op.alter_column('due_trackers', 'advance_balance', existing_type=sa.Numeric(14, 2),
                    type_=sa.Numeric(10, 2), existing_nullable=False)
