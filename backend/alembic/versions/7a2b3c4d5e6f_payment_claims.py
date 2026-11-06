"""Resident payment claims

Revision ID: 7a2b3c4d5e6f
Revises: 6f1a2b3c4d5e
Create Date: 2026-11-06

payment_claims: a resident reporting "I paid" (amount, date, UPI / bank reference, optional screenshot) for the society
office to confirm or reject. Confirming records the payment through the existing online_payment_submissions path and links
it in submission_id. Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = '7a2b3c4d5e6f'
down_revision = '6f1a2b3c4d5e'
branch_labels = None
depends_on    = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'payment_claims' in insp.get_table_names():
        return
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        'payment_claims',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', uuid, sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flat_id', uuid, sa.ForeignKey('flats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bill_id', uuid, sa.ForeignKey('maintenance_bills.id', ondelete='SET NULL'), nullable=True),
        sa.Column('claimed_by', uuid, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_by', uuid, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('submission_id', uuid, sa.ForeignKey('online_payment_submissions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('payment_mode', sa.String(20), nullable=False),
        sa.Column('transaction_ref', sa.String(100), nullable=True),
        sa.Column('bank_name', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('screenshot_data', sa.LargeBinary(), nullable=True),
        sa.Column('screenshot_mime_type', sa.String(50), nullable=True),
        sa.Column('screenshot_file_name', sa.String(255), nullable=True),
    )
    for col in ('society_id', 'flat_id', 'bill_id', 'claimed_by', 'transaction_ref', 'status'):
        op.create_index(f'ix_payment_claims_{col}', 'payment_claims', [col])


def downgrade():
    op.drop_table('payment_claims')
