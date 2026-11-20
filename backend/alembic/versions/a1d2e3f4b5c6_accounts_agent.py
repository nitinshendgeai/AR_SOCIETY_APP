"""Accounts Agent (monitoring outbox, learning profile, findings, proposals, audit)

Revision ID: a1d2e3f4b5c6
Revises: a7c9e1b3d5f2
Create Date: 2026-11-19

Seven new society-scoped tables; nothing existing is altered. Idempotent and reversible.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'a1d2e3f4b5c6'
down_revision = 'a7c9e1b3d5f2'
branch_labels = None
depends_on    = None

TABLES = (
    'accounts_agent_audit_logs', 'accounts_agent_proposals', 'accounts_agent_findings', 'accounts_agent_events',
    'accounts_agent_patterns', 'accounts_agent_learning_runs', 'accounts_agent_settings',
)


def _base():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def _soc():
    return sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'),
                     nullable=False, index=True)


def _user(name):
    return sa.Column(name, UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)


def _create(name, *cols, **kw):
    if name not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(name, *_base(), *cols, **kw)


def upgrade():
    _create('accounts_agent_settings', _soc(),
            sa.Column('monitoring_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('notify_min_severity', sa.String(16), nullable=False, server_default='HIGH'),
            sa.Column('z_threshold', sa.Float(), nullable=False, server_default='3.5'),
            sa.Column('recurring_tolerance_pct', sa.Float(), nullable=False, server_default='10'),
            sa.Column('duplicate_window_days', sa.Integer(), nullable=False, server_default='7'),
            sa.Column('llm_provider', sa.String(30), nullable=False, server_default='disabled'),
            sa.Column('last_monitored_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            _user('updated_by'),
            sa.UniqueConstraint('society_id', name='uq_agent_settings_society'))

    _create('accounts_agent_learning_runs', _soc(),
            sa.Column('window_start', sa.Date(), nullable=False),
            sa.Column('window_end', sa.Date(), nullable=False),
            sa.Column('status', sa.String(16), nullable=False, server_default='running'),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('finished_at', sa.DateTime(), nullable=True),
            sa.Column('voucher_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('line_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('months_covered', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('days_covered', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('pattern_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0'),
            sa.Column('confidence_label', sa.String(16), nullable=False, server_default='none'),
            sa.Column('summary', sa.JSON(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            _user('triggered_by'))
    op.create_index('ix_agent_runs_society_started', 'accounts_agent_learning_runs', ['society_id', 'started_at']) \
        if not _has_index('accounts_agent_learning_runs', 'ix_agent_runs_society_started') else None

    _create('accounts_agent_patterns', _soc(),
            sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('accounts_agent_learning_runs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('pattern_type', sa.String(30), nullable=False),
            sa.Column('pattern_key', sa.String(200), nullable=False),
            sa.Column('sample_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('stats', sa.JSON(), nullable=False),
            sa.UniqueConstraint('society_id', 'pattern_type', 'pattern_key', name='uq_agent_pattern_key'))

    _create('accounts_agent_events', _soc(),
            sa.Column('voucher_id', UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('event_type', sa.String(30), nullable=False),
            sa.Column('idempotency_key', sa.String(160), nullable=False),
            sa.Column('status', sa.String(12), nullable=False, server_default='pending'),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
            sa.Column('locked_until', sa.DateTime(), nullable=True),
            sa.Column('locked_by', sa.String(60), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('processed_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('idempotency_key', name='uq_agent_event_idem'))
    if not _has_index('accounts_agent_events', 'ix_agent_events_claim'):
        op.create_index('ix_agent_events_claim', 'accounts_agent_events', ['status', 'next_attempt_at'])

    _create('accounts_agent_findings', _soc(),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('transaction_ref', sa.String(60), nullable=True),
            sa.Column('category', sa.String(40), nullable=False, index=True),
            sa.Column('finding_class', sa.String(40), nullable=False),
            sa.Column('severity', sa.String(16), nullable=False, index=True),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('rule_code', sa.String(40), nullable=False, index=True),
            sa.Column('dedupe_key', sa.String(200), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('explanation', sa.Text(), nullable=False),
            sa.Column('expected_behaviour', sa.Text(), nullable=True),
            sa.Column('actual_behaviour', sa.Text(), nullable=True),
            sa.Column('evidence', sa.JSON(), nullable=True),
            sa.Column('recommended_action', sa.Text(), nullable=True),
            sa.Column('status', sa.String(16), nullable=False, server_default='NEW'),
            _user('reviewed_by'),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('resolution_note', sa.Text(), nullable=True),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('learning_confidence', sa.String(16), nullable=True),
            sa.Column('source_event_id', UUID(as_uuid=True), nullable=True),
            sa.Column('voucher_date', sa.Date(), nullable=True, index=True),
            sa.UniqueConstraint('society_id', 'dedupe_key', name='uq_agent_finding_dedupe'))
    if not _has_index('accounts_agent_findings', 'ix_agent_findings_list'):
        op.create_index('ix_agent_findings_list', 'accounts_agent_findings',
                        ['society_id', 'status', 'severity', 'created_at'])

    _create('accounts_agent_proposals', _soc(),
            sa.Column('finding_id', UUID(as_uuid=True), sa.ForeignKey('accounts_agent_findings.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('action_type', sa.String(20), nullable=False),
            sa.Column('status', sa.String(12), nullable=False, server_default='PENDING'),
            sa.Column('voucher_fingerprint', sa.String(64), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('explanation', sa.Text(), nullable=False),
            sa.Column('before_values', sa.JSON(), nullable=False),
            sa.Column('after_values', sa.JSON(), nullable=True),
            sa.Column('impact', sa.JSON(), nullable=True),
            sa.Column('executable', sa.Boolean(), nullable=False, server_default=sa.true()),
            _user('created_by'), _user('decided_by'),
            sa.Column('decided_at', sa.DateTime(), nullable=True),
            sa.Column('decision_note', sa.Text(), nullable=True),
            sa.Column('result', sa.JSON(), nullable=True))
    if not _has_index('accounts_agent_proposals', 'ix_agent_proposals_list'):
        op.create_index('ix_agent_proposals_list', 'accounts_agent_proposals', ['society_id', 'status', 'created_at'])

    _create('accounts_agent_audit_logs', _soc(),
            _user('actor_id'),
            sa.Column('action', sa.String(40), nullable=False, index=True),
            sa.Column('entity_type', sa.String(30), nullable=False),
            sa.Column('entity_id', sa.String(64), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True))
    if not _has_index('accounts_agent_audit_logs', 'ix_agent_audit_society_created'):
        op.create_index('ix_agent_audit_society_created', 'accounts_agent_audit_logs', ['society_id', 'created_at'])


def _has_index(table, name) -> bool:
    insp = sa.inspect(op.get_bind())
    return table in insp.get_table_names() and name in {i['name'] for i in insp.get_indexes(table)}


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for t in TABLES:
        if t in existing:
            op.drop_table(t)
