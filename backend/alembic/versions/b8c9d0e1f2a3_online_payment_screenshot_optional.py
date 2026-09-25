"""online_payment_submissions.screenshot_* nullable

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-22

The payment-recording form now covers cash and cheque too, neither of
which has a screenshot to attach (only the online payment modes — UPI,
bank transfer, NEFT, RTGS, online gateway — require one, enforced in
BillingService, not the DB). Relax screenshot_data/screenshot_mime_type
from NOT NULL to nullable; existing rows already have both set, so this
is a pure constraint relaxation, safe on a populated table.
"""
from alembic import op
import sqlalchemy as sa

revision      = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.alter_column('online_payment_submissions', 'screenshot_data',
                     existing_type=sa.LargeBinary(), nullable=True)
    op.alter_column('online_payment_submissions', 'screenshot_mime_type',
                     existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.alter_column('online_payment_submissions', 'screenshot_mime_type',
                     existing_type=sa.String(50), nullable=False)
    op.alter_column('online_payment_submissions', 'screenshot_data',
                     existing_type=sa.LargeBinary(), nullable=False)
