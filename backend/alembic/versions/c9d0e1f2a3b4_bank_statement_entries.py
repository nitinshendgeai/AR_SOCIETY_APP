"""bank statement entries for reconciliation matching

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-23

Adds bank_statement_entries: imported rows from a society's bank
statement, matched against OnlinePaymentSubmission rows to close the
reconciliation loop (see BillingService.confirm_bank_match). Purely
additive — new table only.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision      = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on    = None

bank_statement_match_status = postgresql.ENUM(
    'unmatched', 'matched', 'ignored',
    name='bankstatementmatchstatus',
)


def upgrade() -> None:
    bank_statement_match_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'bank_statement_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),

        sa.Column('society_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('imported_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('matched_submission_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('matched_by', postgresql.UUID(as_uuid=True), nullable=True),

        sa.Column('txn_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),

        sa.Column('match_status', bank_statement_match_status, nullable=False, server_default='unmatched'),
        sa.Column('matched_at', sa.DateTime(), nullable=True),
        sa.Column('ignore_reason', sa.Text(), nullable=True),

        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['imported_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['matched_submission_id'], ['online_payment_submissions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['matched_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_bank_statement_entries_society_id', 'bank_statement_entries', ['society_id'])
    op.create_index('ix_bank_statement_entries_matched_submission_id', 'bank_statement_entries', ['matched_submission_id'])
    op.create_index('ix_bank_statement_entries_txn_date', 'bank_statement_entries', ['txn_date'])
    op.create_index('ix_bank_statement_entries_reference', 'bank_statement_entries', ['reference'])
    op.create_index('ix_bank_statement_entries_match_status', 'bank_statement_entries', ['match_status'])


def downgrade() -> None:
    op.drop_index('ix_bank_statement_entries_match_status', table_name='bank_statement_entries')
    op.drop_index('ix_bank_statement_entries_reference', table_name='bank_statement_entries')
    op.drop_index('ix_bank_statement_entries_txn_date', table_name='bank_statement_entries')
    op.drop_index('ix_bank_statement_entries_matched_submission_id', table_name='bank_statement_entries')
    op.drop_index('ix_bank_statement_entries_society_id', table_name='bank_statement_entries')
    op.drop_table('bank_statement_entries')
    bank_statement_match_status.drop(op.get_bind(), checkfirst=True)
