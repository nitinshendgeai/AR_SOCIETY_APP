"""saas_trial_onboarding_platform_admin

Revision ID: f8a9b0c1d2e3
Revises: 259b1102d3cd
Create Date: 2026-06-05

Changes:
  ALTER societies: trial fields, subscription fields, setup tracking, contact person
  ALTER users: terms_accepted, setup_completed
"""
from alembic import op
import sqlalchemy as sa

revision      = 'f8a9b0c1d2e3'
down_revision = '259b1102d3cd'
branch_labels = None
depends_on    = None


def upgrade() -> None:

    # ── ALTER societies ───────────────────────────────────────────────────────

    # Trial / subscription status
    acct_status = sa.Enum(
        'TRIAL', 'ACTIVE', 'EXPIRED', 'SUSPENDED', 'CANCELLED',
        name='accountstatus',
    )
    acct_status.create(op.get_bind(), checkfirst=True)

    op.add_column('societies', sa.Column('account_status',
        sa.Enum('TRIAL', 'ACTIVE', 'EXPIRED', 'SUSPENDED', 'CANCELLED',
                name='accountstatus', create_constraint=False),
        nullable=False, server_default='TRIAL'))
    op.add_column('societies', sa.Column('is_trial',
        sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('societies', sa.Column('trial_start_date',
        sa.Date(), nullable=True))
    op.add_column('societies', sa.Column('trial_end_date',
        sa.Date(), nullable=True))

    # Subscription (nullable until upgraded from trial)
    op.add_column('societies', sa.Column('subscription_plan',
        sa.String(50), nullable=True))
    op.add_column('societies', sa.Column('subscription_status',
        sa.String(50), nullable=True))
    op.add_column('societies', sa.Column('subscription_start_date',
        sa.Date(), nullable=True))
    op.add_column('societies', sa.Column('subscription_expiry_date',
        sa.Date(), nullable=True))

    # Usage limits
    op.add_column('societies', sa.Column('allowed_users',
        sa.Integer(), nullable=False, server_default='50'))
    op.add_column('societies', sa.Column('allowed_flats',
        sa.Integer(), nullable=False, server_default='100'))
    op.add_column('societies', sa.Column('allowed_storage_mb',
        sa.Integer(), nullable=False, server_default='1024'))

    # Contact person (registered by)
    op.add_column('societies', sa.Column('contact_person_name',
        sa.String(255), nullable=True))

    # Setup wizard tracking
    op.add_column('societies', sa.Column('setup_completed',
        sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('societies', sa.Column('setup_completion_percentage',
        sa.Integer(), nullable=False, server_default='0'))

    # ── ALTER users ───────────────────────────────────────────────────────────

    op.add_column('users', sa.Column('terms_accepted',
        sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('setup_completed',
        sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # users
    op.drop_column('users', 'setup_completed')
    op.drop_column('users', 'terms_accepted')

    # societies
    for col in [
        'setup_completion_percentage', 'setup_completed',
        'contact_person_name',
        'allowed_storage_mb', 'allowed_flats', 'allowed_users',
        'subscription_expiry_date', 'subscription_start_date',
        'subscription_status', 'subscription_plan',
        'trial_end_date', 'trial_start_date', 'is_trial', 'account_status',
    ]:
        op.drop_column('societies', col)

    sa.Enum(name='accountstatus').drop(op.get_bind(), checkfirst=True)
