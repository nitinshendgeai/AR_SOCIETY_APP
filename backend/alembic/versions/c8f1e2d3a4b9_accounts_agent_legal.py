"""Accounts Agent — legal & bye-law intelligence (profile, documents, clauses, versioned rules, legal reviews,
resolutions, budgets, compliance calendar) and the legal columns on findings.

Revision ID: c8f1e2d3a4b9
Revises: a1d2e3f4b5c6
Create Date: 2026-11-19

Eight new society-scoped tables (jurisdiction-wide law rows have a NULL society_id) and six nullable/defaulted columns
added to accounts_agent_findings. No existing accounting table is touched. Idempotent and reversible. The Maharashtra
rule pack is NOT inserted here: it is seeded at runtime (legal/seed.py) so it is never silently overwritten.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'c8f1e2d3a4b9'
down_revision = 'a1d2e3f4b5c6'
branch_labels = None
depends_on    = None

TABLES = (
    'accounts_agent_compliance_items', 'accounts_agent_budget_lines', 'accounts_agent_resolutions',
    'accounts_agent_legal_reviews', 'accounts_agent_legal_rules', 'accounts_agent_legal_clauses',
    'accounts_agent_legal_profiles', 'accounts_agent_legal_documents',
)
FINDING_COLUMNS = ('engine', 'compliance_category', 'legal_rule_code', 'legal_source', 'flat_id', 'vendor_id')


def _base():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def _soc(nullable=False):
    return sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'),
                     nullable=nullable, index=True)


def _user(name):
    return sa.Column(name, UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)


def _fk(name, table, nullable=True, ondelete='SET NULL'):
    return sa.Column(name, UUID(as_uuid=True), sa.ForeignKey(f'{table}.id', ondelete=ondelete), nullable=nullable)


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create(name, *cols, **kw):
    if name not in _tables():
        op.create_table(name, *_base(), *cols, **kw)


def upgrade():
    _create('accounts_agent_legal_documents', _soc(True),
            sa.Column('jurisdiction', sa.String(20), nullable=False, server_default='IN-MH'),
            sa.Column('document_type', sa.String(40), nullable=False),
            sa.Column('source_level', sa.String(1), nullable=False),
            sa.Column('title', sa.String(300), nullable=False),
            sa.Column('source_authority', sa.String(200), nullable=True),
            sa.Column('source_url', sa.String(500), nullable=True),
            sa.Column('is_primary_source', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('reference_number', sa.String(120), nullable=True),
            sa.Column('file_name', sa.String(255), nullable=False),
            sa.Column('mime_type', sa.String(120), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('data', sa.LargeBinary(), nullable=False),
            sa.Column('sha256', sa.String(64), nullable=False, index=True),
            sa.Column('language', sa.String(10), nullable=False, server_default='unknown'),
            sa.Column('extracted_text', sa.Text(), nullable=True),
            sa.Column('pages', sa.JSON(), nullable=True),
            sa.Column('page_count', sa.Integer(), nullable=True),
            sa.Column('extraction_method', sa.String(30), nullable=True),
            sa.Column('extraction_quality', sa.String(20), nullable=False, server_default='NONE'),
            sa.Column('extraction_issues', sa.JSON(), nullable=True),
            sa.Column('issue_date', sa.Date(), nullable=True),
            sa.Column('approval_date', sa.Date(), nullable=True),
            sa.Column('effective_from', sa.Date(), nullable=True),
            sa.Column('effective_until', sa.Date(), nullable=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='UNVERIFIED'),
            sa.Column('requested_status', sa.String(30), nullable=True),
            sa.Column('verification_status', sa.String(30), nullable=False, server_default='PENDING_VERIFICATION'),
            _user('verified_by'),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('verification_note', sa.Text(), nullable=True),
            _fk('superseded_by_id', 'accounts_agent_legal_documents'),
            _fk('duplicate_of_id', 'accounts_agent_legal_documents'),
            _user('uploaded_by'),
            sa.Index('ix_agent_legal_docs_scope', 'society_id', 'document_type', 'status'))

    _create('accounts_agent_legal_profiles', _soc(),
            sa.Column('registration_number', sa.String(100), nullable=True),
            sa.Column('society_name', sa.String(255), nullable=True),
            sa.Column('registration_date', sa.Date(), nullable=True),
            sa.Column('classification', sa.String(80), nullable=True),
            sa.Column('society_type', sa.String(40), nullable=False, server_default='housing'),
            sa.Column('number_of_units', sa.Integer(), nullable=True),
            sa.Column('number_of_members', sa.Integer(), nullable=True),
            sa.Column('state', sa.String(100), nullable=True),
            sa.Column('district', sa.String(100), nullable=True),
            sa.Column('jurisdiction', sa.String(20), nullable=False, server_default='IN-MH'),
            sa.Column('financial_year_start_month', sa.Integer(), nullable=False, server_default='4'),
            _fk('registered_bylaw_document_id', 'accounts_agent_legal_documents'),
            sa.Column('registered_bylaw_version', sa.String(60), nullable=True),
            sa.Column('approved_amendments', sa.JSON(), nullable=True),
            sa.Column('adopted_model_bylaw_version', sa.String(60), nullable=True),
            sa.Column('legal_verification_status', sa.String(30), nullable=False, server_default='PENDING_VERIFICATION'),
            sa.Column('last_legal_review_date', sa.Date(), nullable=True),
            _user('updated_by'),
            sa.UniqueConstraint('society_id', name='uq_agent_legal_profile_society'))

    _create('accounts_agent_legal_clauses',
            _fk('document_id', 'accounts_agent_legal_documents', nullable=False, ondelete='CASCADE'),
            _soc(True),
            sa.Column('clause_ref', sa.String(60), nullable=False),
            sa.Column('heading', sa.String(300), nullable=True),
            sa.Column('page_number', sa.Integer(), nullable=True),
            sa.Column('language', sa.String(10), nullable=False, server_default='unknown'),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('needs_verification', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('verified', sa.Boolean(), nullable=False, server_default=sa.false()),
            _user('verified_by'))
    if 'accounts_agent_legal_clauses' in _tables():
        idx = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('accounts_agent_legal_clauses')}
        if 'ix_accounts_agent_legal_clauses_document_id' not in idx:
            op.create_index('ix_accounts_agent_legal_clauses_document_id', 'accounts_agent_legal_clauses', ['document_id'])

    _create('accounts_agent_legal_rules',
            sa.Column('scope', sa.String(40), nullable=False),
            _soc(True),
            sa.Column('rule_code', sa.String(60), nullable=False, index=True),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('topic', sa.String(80), nullable=False),
            sa.Column('jurisdiction', sa.String(20), nullable=False, server_default='IN-MH'),
            sa.Column('society_type', sa.String(40), nullable=False, server_default='housing'),
            sa.Column('rule_category', sa.String(40), nullable=False),
            sa.Column('title', sa.String(300), nullable=False),
            sa.Column('source_level', sa.String(1), nullable=False),
            _fk('source_document_id', 'accounts_agent_legal_documents'),
            sa.Column('source_document_title', sa.String(300), nullable=True),
            sa.Column('source_authority', sa.String(200), nullable=True),
            sa.Column('act_section', sa.String(60), nullable=True),
            sa.Column('rule_number', sa.String(60), nullable=True),
            sa.Column('bye_law_number', sa.String(60), nullable=True),
            sa.Column('clause_reference', sa.String(120), nullable=True),
            sa.Column('page_number', sa.String(30), nullable=True),
            sa.Column('original_text', sa.Text(), nullable=True),
            sa.Column('translated_text', sa.Text(), nullable=True),
            sa.Column('publication_date', sa.Date(), nullable=True),
            sa.Column('effective_from', sa.Date(), nullable=True),
            sa.Column('effective_until', sa.Date(), nullable=True),
            sa.Column('legal_status', sa.String(20), nullable=False, server_default='UNVERIFIED'),
            sa.Column('verification_status', sa.String(30), nullable=False, server_default='PENDING_VERIFICATION'),
            sa.Column('applicability_conditions', sa.JSON(), nullable=True),
            sa.Column('calculation_method', sa.JSON(), nullable=True),
            sa.Column('validation_expression', sa.String(300), nullable=True),
            sa.Column('required_evidence', sa.JSON(), nullable=True),
            sa.Column('severity', sa.String(16), nullable=False, server_default='MEDIUM'),
            sa.Column('human_review_required', sa.Boolean(), nullable=False, server_default=sa.true()),
            _fk('superseded_by_id', 'accounts_agent_legal_rules'),
            sa.Column('last_verified_at', sa.DateTime(), nullable=True),
            _user('verified_by'),
            sa.Column('verification_note', sa.Text(), nullable=True),
            sa.Column('change_note', sa.Text(), nullable=True),
            _user('created_by'),
            sa.UniqueConstraint('scope', 'rule_code', 'version', name='uq_agent_legal_rule_version'),
            sa.Index('ix_agent_legal_rules_topic', 'scope', 'topic', 'effective_from'))

    _create('accounts_agent_legal_reviews',
            sa.Column('scope', sa.String(40), nullable=False),
            _soc(True),
            sa.Column('review_type', sa.String(30), nullable=False),
            sa.Column('title', sa.String(300), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('rule_codes', sa.JSON(), nullable=True),
            sa.Column('document_ids', sa.JSON(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('blocking', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('status', sa.String(16), nullable=False, server_default='OPEN', index=True),
            sa.Column('dedupe_key', sa.String(200), nullable=False),
            _user('decided_by'),
            sa.Column('decided_at', sa.DateTime(), nullable=True),
            sa.Column('decision', sa.String(40), nullable=True),
            sa.Column('decision_note', sa.Text(), nullable=True),
            sa.UniqueConstraint('scope', 'dedupe_key', name='uq_agent_legal_review_dedupe'))

    _create('accounts_agent_resolutions', _soc(),
            sa.Column('resolution_number', sa.String(60), nullable=False),
            sa.Column('meeting_type', sa.String(12), nullable=False),
            sa.Column('meeting_date', sa.Date(), nullable=False),
            sa.Column('notice_date', sa.Date(), nullable=True),
            sa.Column('agenda', sa.Text(), nullable=True),
            sa.Column('attendance', sa.Integer(), nullable=True),
            sa.Column('quorum_required', sa.Integer(), nullable=True),
            sa.Column('votes_for', sa.Integer(), nullable=True),
            sa.Column('votes_against', sa.Integer(), nullable=True),
            sa.Column('votes_abstain', sa.Integer(), nullable=True),
            sa.Column('approval_authority', sa.String(24), nullable=False),
            sa.Column('category', sa.String(24), nullable=False, server_default='other'),
            sa.Column('purpose', sa.Text(), nullable=False),
            sa.Column('approved_amount', sa.Numeric(14, 2), nullable=True),
            _fk('vendor_id', 'vendors'), _fk('account_id', 'accounts'), _fk('work_order_id', 'work_orders'),
            _fk('contract_id', 'amc_contracts'),
            sa.Column('conditions', sa.Text(), nullable=True),
            sa.Column('period_from', sa.Date(), nullable=True),
            sa.Column('period_to', sa.Date(), nullable=True),
            _fk('supporting_document_id', 'accounts_agent_legal_documents'),
            _fk('governance_resolution_id', 'meeting_resolutions'),
            sa.Column('status', sa.String(16), nullable=False, server_default='RECORDED'),
            _fk('supersedes_id', 'accounts_agent_resolutions'),
            _user('verified_by'),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            _user('created_by'),
            sa.Index('ix_agent_resolutions_society', 'society_id', 'meeting_date'))

    _create('accounts_agent_budget_lines', _soc(),
            sa.Column('fiscal_year', sa.String(7), nullable=False),
            _fk('account_id', 'accounts', nullable=False, ondelete='CASCADE'),
            sa.Column('approved_amount', sa.Numeric(14, 2), nullable=False),
            _fk('resolution_id', 'accounts_agent_resolutions'),
            sa.Column('note', sa.Text(), nullable=True),
            _user('updated_by'),
            sa.UniqueConstraint('society_id', 'fiscal_year', 'account_id', name='uq_agent_budget_line'))

    _create('accounts_agent_compliance_items', _soc(),
            sa.Column('code', sa.String(60), nullable=False),
            sa.Column('title', sa.String(300), nullable=False),
            sa.Column('category', sa.String(30), nullable=False),
            sa.Column('legal_rule_code', sa.String(60), nullable=True),
            sa.Column('legal_source', sa.Text(), nullable=True),
            sa.Column('applicability', sa.String(40), nullable=False, server_default='PROFESSIONAL_VERIFICATION_REQUIRED'),
            sa.Column('applicability_reason', sa.Text(), nullable=True),
            sa.Column('responsible_role', sa.String(60), nullable=True),
            sa.Column('financial_period', sa.String(7), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('due_date_basis', sa.Text(), nullable=True),
            sa.Column('supporting_documents', sa.JSON(), nullable=True),
            sa.Column('completion_status', sa.String(20), nullable=False, server_default='PENDING'),
            sa.Column('completed_on', sa.Date(), nullable=True),
            sa.Column('evidence_ref', sa.String(200), nullable=True),
            sa.Column('verification_status', sa.String(30), nullable=False, server_default='PENDING_VERIFICATION'),
            _user('updated_by'),
            sa.UniqueConstraint('society_id', 'code', 'financial_period', name='uq_agent_compliance_item'))

    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('accounts_agent_findings')}
    adds = [
        sa.Column('engine', sa.String(12), nullable=False, server_default='accounting'),
        sa.Column('compliance_category', sa.String(40), nullable=True),
        sa.Column('legal_rule_code', sa.String(60), nullable=True),
        sa.Column('legal_source', sa.JSON(), nullable=True),
        sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='SET NULL',
                                                               name='fk_agent_findings_flat'), nullable=True),
        sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='SET NULL',
                                                                 name='fk_agent_findings_vendor'), nullable=True),
    ]
    with op.batch_alter_table('accounts_agent_findings') as b:
        for c in adds:
            if c.name not in cols:
                b.add_column(c)
    idx = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('accounts_agent_findings')}
    if 'ix_accounts_agent_findings_legal_rule_code' not in idx:
        op.create_index('ix_accounts_agent_findings_legal_rule_code', 'accounts_agent_findings', ['legal_rule_code'])


def downgrade():
    idx = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('accounts_agent_findings')}
    if 'ix_accounts_agent_findings_legal_rule_code' in idx:
        op.drop_index('ix_accounts_agent_findings_legal_rule_code', table_name='accounts_agent_findings')
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('accounts_agent_findings')}
    with op.batch_alter_table('accounts_agent_findings') as b:
        for name in FINDING_COLUMNS:
            if name in cols:
                b.drop_column(name)
    existing = _tables()
    for t in TABLES:
        if t in existing:
            op.drop_table(t)
