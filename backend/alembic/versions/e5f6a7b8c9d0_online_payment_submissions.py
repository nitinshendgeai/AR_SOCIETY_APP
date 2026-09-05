"""online_payment_submissions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-05

Table: online_payment_submissions

FMC Manager records a resident's online (UPI/bank transfer) payment
screenshot against a Wing + Flat, for later bank reconciliation. This is
deliberately independent of maintenance_bills/payment_receipts — capturing
what a resident says they paid doesn't require an existing bill to apply
against; `bill_id` is a nullable link set once someone reconciles the
entry against a bill. The screenshot itself is stored inline (bytea) since
the backend's container filesystem is ephemeral on Railway and a
disk-stored file would be lost on redeploy.

New table only — safe to run against a database that already has data.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'online_payment_submissions' not in existing_tables:
        op.create_table(
            'online_payment_submissions',
            sa.Column('id',                    UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at',            sa.DateTime(), nullable=False),
            sa.Column('updated_at',            sa.DateTime(), nullable=False),
            sa.Column('is_active',             sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('society_id',            UUID(as_uuid=True), nullable=False),
            sa.Column('wing_id',               UUID(as_uuid=True), nullable=True),
            sa.Column('flat_id',               UUID(as_uuid=True), nullable=False),
            sa.Column('bill_id',               UUID(as_uuid=True), nullable=True),
            sa.Column('recorded_by',           UUID(as_uuid=True), nullable=True),
            sa.Column('reviewed_by',           UUID(as_uuid=True), nullable=True),
            sa.Column('receipt_number',        sa.String(30), nullable=False),
            sa.Column('amount',                sa.Numeric(12, 2), nullable=False),
            sa.Column('payment_date',          sa.Date(), nullable=False),
            sa.Column('payment_mode',          sa.String(30), nullable=False),
            sa.Column('transaction_ref',       sa.String(100), nullable=True),
            sa.Column('bank_name',             sa.String(100), nullable=True),
            sa.Column('notes',                 sa.Text(), nullable=True),
            sa.Column('status',                sa.String(20), nullable=False, server_default='pending'),
            sa.Column('reviewed_at',           sa.DateTime(), nullable=True),
            sa.Column('review_notes',          sa.Text(), nullable=True),
            sa.Column('screenshot_data',       sa.LargeBinary(), nullable=False),
            sa.Column('screenshot_mime_type',  sa.String(50), nullable=False, server_default='image/jpeg'),
            sa.Column('screenshot_file_name',  sa.String(255), nullable=True),
            sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['wing_id'], ['wings.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['flat_id'], ['flats.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['bill_id'], ['maintenance_bills.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
            sa.UniqueConstraint('receipt_number', name='uq_online_payment_submissions_receipt_number'),
        )
        op.create_index('ix_online_payment_submissions_society_id', 'online_payment_submissions', ['society_id'])
        op.create_index('ix_online_payment_submissions_wing_id', 'online_payment_submissions', ['wing_id'])
        op.create_index('ix_online_payment_submissions_flat_id', 'online_payment_submissions', ['flat_id'])
        op.create_index('ix_online_payment_submissions_bill_id', 'online_payment_submissions', ['bill_id'])
        op.create_index('ix_online_payment_submissions_receipt_number', 'online_payment_submissions', ['receipt_number'])
        op.create_index('ix_online_payment_submissions_payment_date', 'online_payment_submissions', ['payment_date'])
        op.create_index('ix_online_payment_submissions_payment_mode', 'online_payment_submissions', ['payment_mode'])
        op.create_index('ix_online_payment_submissions_transaction_ref', 'online_payment_submissions', ['transaction_ref'])
        op.create_index('ix_online_payment_submissions_status', 'online_payment_submissions', ['status'])


def downgrade() -> None:
    op.drop_table('online_payment_submissions')
