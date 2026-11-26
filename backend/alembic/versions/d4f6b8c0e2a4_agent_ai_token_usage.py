"""Accounts Agent: AI token budget, usage ledger and reusable answers

Revision ID: d4f6b8c0e2a4
Revises: c3e5a7b9d1f2
Create Date: 2026-11-26

* accounts_agent_settings.ai_monthly_token_budget (default 300,000): the most AI tokens a society spends in a month.
* accounts_agent_ai_usage: tokens spent and saved per society, month and feature.
* accounts_agent_ai_answers: AI-worded answers kept so the same question on the same clauses costs no tokens.
Additive, idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'd4f6b8c0e2a4'
down_revision = 'c3e5a7b9d1f2'
branch_labels = None
depends_on    = None


def _base():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'),
                  nullable=False, index=True),
    ]


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('accounts_agent_settings')}
    if 'ai_monthly_token_budget' not in cols:
        op.add_column('accounts_agent_settings',
                      sa.Column('ai_monthly_token_budget', sa.Integer(), nullable=False, server_default='300000'))
    tables = set(insp.get_table_names())
    if 'accounts_agent_ai_usage' not in tables:
        op.create_table(
            'accounts_agent_ai_usage', *_base(),
            sa.Column('month', sa.String(7), nullable=False),
            sa.Column('feature', sa.String(30), nullable=False),
            *[sa.Column(n, sa.Integer(), nullable=False, server_default='0') for n in (
                'ai_calls', 'input_tokens', 'output_tokens', 'reused_answers', 'answered_locally', 'over_budget',
                'failed_calls')],
            sa.UniqueConstraint('society_id', 'month', 'feature', name='uq_agent_ai_usage'))
    if 'accounts_agent_ai_answers' not in tables:
        op.create_table(
            'accounts_agent_ai_answers', *_base(),
            sa.Column('feature', sa.String(30), nullable=False),
            sa.Column('key', sa.String(64), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('hits', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('society_id', 'feature', 'key', name='uq_agent_ai_answer'))


def downgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for t in ('accounts_agent_ai_answers', 'accounts_agent_ai_usage'):
        if t in tables:
            op.drop_table(t)
    cols = {c['name'] for c in insp.get_columns('accounts_agent_settings')}
    if 'ai_monthly_token_budget' in cols:
        op.drop_column('accounts_agent_settings', 'ai_monthly_token_budget')
