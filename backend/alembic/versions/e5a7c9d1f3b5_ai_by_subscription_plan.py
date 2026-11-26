"""AI tied to the subscription: per-plan allowances and per-society overrides

Revision ID: e5a7c9d1f3b5
Revises: d4f6b8c0e2a4
Create Date: 2026-11-26

* platform_ai_plans: which plans include AI and how many tokens (a month; for 'trial', for the whole trial). Seeded:
  trial 50,000 (whole trial); starter none; growth 300,000 a month; enterprise 1,000,000 a month.
* accounts_agent_settings.ai_plan_override / ai_override_tokens: the platform administrator's per-society override.
* accounts_agent_ai_usage.not_included: requests that wanted AI the subscription does not include.
Additive, idempotent and reversible.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'e5a7c9d1f3b5'
down_revision = 'd4f6b8c0e2a4'
branch_labels = None
depends_on    = None

DEFAULTS = (('trial', True, 50000), ('starter', False, 0), ('growth', True, 300000), ('enterprise', True, 1000000))


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'platform_ai_plans' not in insp.get_table_names():
        op.create_table(
            'platform_ai_plans',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('plan_key', sa.String(30), nullable=False, unique=True),
            sa.Column('ai_included', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('monthly_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('updated_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
        table = sa.table('platform_ai_plans', sa.column('id', UUID(as_uuid=True)), sa.column('created_at', sa.DateTime()),
                         sa.column('updated_at', sa.DateTime()), sa.column('is_active', sa.Boolean()),
                         sa.column('plan_key', sa.String()), sa.column('ai_included', sa.Boolean()),
                         sa.column('monthly_tokens', sa.Integer()))
        now = datetime.utcnow()
        op.bulk_insert(table, [{'id': uuid.uuid4(), 'created_at': now, 'updated_at': now, 'is_active': True,
                                'plan_key': k, 'ai_included': inc, 'monthly_tokens': n} for k, inc, n in DEFAULTS])
    cols = {c['name'] for c in insp.get_columns('accounts_agent_settings')}
    if 'ai_plan_override' not in cols:
        op.add_column('accounts_agent_settings', sa.Column('ai_plan_override', sa.String(8), nullable=True))
    if 'ai_override_tokens' not in cols:
        op.add_column('accounts_agent_settings', sa.Column('ai_override_tokens', sa.Integer(), nullable=True))
    cols = {c['name'] for c in insp.get_columns('accounts_agent_ai_usage')}
    if 'not_included' not in cols:
        op.add_column('accounts_agent_ai_usage',
                      sa.Column('not_included', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if 'not_included' in {c['name'] for c in insp.get_columns('accounts_agent_ai_usage')}:
        op.drop_column('accounts_agent_ai_usage', 'not_included')
    cols = {c['name'] for c in insp.get_columns('accounts_agent_settings')}
    for c in ('ai_override_tokens', 'ai_plan_override'):
        if c in cols:
            op.drop_column('accounts_agent_settings', c)
    if 'platform_ai_plans' in insp.get_table_names():
        op.drop_table('platform_ai_plans')
