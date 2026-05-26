"""vendor_amc_management_module

Revision ID: 5805225fd93e
Revises: 9090d9f22565
Create Date: 2026-05-26

Tables: vendors, vendor_services, amc_contracts, amc_service_schedules,
        service_requests, service_visit_logs, vendor_invoices
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '5805225fd93e'
down_revision = '9090d9f22565'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    vendor_cat_e  = sa.Enum('electrical','plumbing','lift','security','housekeeping','gardening',
                            'pest_control','cctv','water_supply','generator','civil','it','other',
                            name='vendorcategory')
    vendor_st_e   = sa.Enum('active','inactive','blacklisted','under_review', name='vendorstatus')
    contract_st_e = sa.Enum('draft','active','expired','renewed','terminated', name='contractstatus')
    svc_freq_e    = sa.Enum('weekly','fortnightly','monthly','quarterly','half_yearly','yearly','on_call',
                            name='servicefrequency')
    sr_status_e   = sa.Enum('open','assigned','scheduled','in_progress','completed','verified','closed','cancelled',
                            name='servicerequeststatus')
    sr_priority_e = sa.Enum('low','medium','high','critical', name='servicerequestpriority')
    sched_st_e    = sa.Enum('scheduled','completed','missed','rescheduled', name='schedulestatus')

    # ── vendors ───────────────────────────────────────────────────────────────
    op.create_table('vendors',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_code',    sa.String(20), nullable=False),
        sa.Column('company_name',   sa.String(255), nullable=False),
        sa.Column('contact_person', sa.String(255), nullable=True),
        sa.Column('mobile',         sa.String(20), nullable=False),
        sa.Column('email',          sa.String(255), nullable=True),
        sa.Column('category',       vendor_cat_e, nullable=False),
        sa.Column('status',         vendor_st_e, nullable=False, server_default='active'),
        sa.Column('address',        sa.Text(), nullable=True),
        sa.Column('city',           sa.String(100), nullable=True),
        sa.Column('pincode',        sa.String(10), nullable=True),
        sa.Column('gst_number',     sa.String(20), nullable=True),
        sa.Column('pan_number',     sa.String(20), nullable=True),
        sa.Column('bank_account',   sa.String(50), nullable=True),
        sa.Column('bank_name',      sa.String(100), nullable=True),
        sa.Column('bank_ifsc',      sa.String(20), nullable=True),
        sa.Column('rating',         sa.Float(), nullable=True),
        sa.Column('total_services', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('services_on_time',sa.Integer(), nullable=False, server_default='0'),
        sa.Column('agreement_doc_url',sa.String(500), nullable=True),
        sa.Column('insurance_expiry',sa.Date(), nullable=True),
        sa.Column('notes',          sa.Text(), nullable=True),
        sa.Column('blacklist_reason',sa.Text(), nullable=True),
        sa.Column('registered_by',  UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],    ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['registered_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_vendors_id',          'vendors', ['id'])
    op.create_index('ix_vendors_vendor_code', 'vendors', ['vendor_code'], unique=True)
    op.create_index('ix_vendors_society_id',  'vendors', ['society_id'])
    op.create_index('ix_vendors_category',    'vendors', ['category'])
    op.create_index('ix_vendors_status',      'vendors', ['status'])
    op.create_index('ix_vendors_mobile',      'vendors', ['mobile'])
    op.create_index('ix_vendors_gst',         'vendors', ['gst_number'])
    op.create_index('ix_vendors_company',     'vendors', ['company_name'])

    # ── vendor_services ───────────────────────────────────────────────────────
    op.create_table('vendor_services',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',    sa.DateTime(), nullable=False),
        sa.Column('updated_at',    sa.DateTime(), nullable=False),
        sa.Column('is_active',     sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('vendor_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('service_name',  sa.String(150), nullable=False),
        sa.Column('category',      vendor_cat_e, nullable=False),
        sa.Column('rate_per_visit',sa.Numeric(10,2), nullable=True),
        sa.Column('rate_per_hour', sa.Numeric(8,2), nullable=True),
        sa.Column('description',   sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_vendor_services_id',        'vendor_services', ['id'])
    op.create_index('ix_vendor_services_vendor_id', 'vendor_services', ['vendor_id'])

    # ── amc_contracts ─────────────────────────────────────────────────────────
    op.create_table('amc_contracts',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',          sa.DateTime(), nullable=False),
        sa.Column('updated_at',          sa.DateTime(), nullable=False),
        sa.Column('is_active',           sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id',           UUID(as_uuid=True), nullable=False),
        sa.Column('asset_id',            UUID(as_uuid=True), nullable=True),
        sa.Column('created_by',          UUID(as_uuid=True), nullable=True),
        sa.Column('contract_number',     sa.String(50), nullable=False),
        sa.Column('contract_name',       sa.String(255), nullable=False),
        sa.Column('category',            vendor_cat_e, nullable=False),
        sa.Column('status',              contract_st_e, nullable=False, server_default='draft'),
        sa.Column('start_date',          sa.Date(), nullable=False),
        sa.Column('end_date',            sa.Date(), nullable=False),
        sa.Column('auto_renew',          sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('renewal_notice_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('service_frequency',   svc_freq_e, nullable=False),
        sa.Column('sla_response_hours',  sa.Integer(), nullable=True),
        sa.Column('scope_of_work',       sa.Text(), nullable=True),
        sa.Column('inclusions',          sa.Text(), nullable=True),
        sa.Column('exclusions',          sa.Text(), nullable=True),
        sa.Column('annual_value',        sa.Numeric(12,2), nullable=True),
        sa.Column('payment_terms',       sa.String(255), nullable=True),
        sa.Column('document_url',        sa.String(500), nullable=True),
        sa.Column('alert_sent_60',       sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('alert_sent_30',       sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('alert_sent_7',        sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('renewed_from_id',     UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'],  ['vendors.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_amc_contracts_id',             'amc_contracts', ['id'])
    op.create_index('ix_amc_contracts_contract_number','amc_contracts', ['contract_number'], unique=True)
    op.create_index('ix_amc_contracts_society_id',     'amc_contracts', ['society_id'])
    op.create_index('ix_amc_contracts_vendor_id',      'amc_contracts', ['vendor_id'])
    op.create_index('ix_amc_contracts_asset_id',       'amc_contracts', ['asset_id'])
    op.create_index('ix_amc_contracts_status',         'amc_contracts', ['status'])
    op.create_index('ix_amc_contracts_end_date',       'amc_contracts', ['end_date'])
    op.create_index('ix_amc_contracts_start_date',     'amc_contracts', ['start_date'])

    # ── amc_service_schedules ─────────────────────────────────────────────────
    op.create_table('amc_service_schedules',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('contract_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('status',         sched_st_e, nullable=False, server_default='scheduled'),
        sa.Column('completed_date', sa.Date(), nullable=True),
        sa.Column('notes',          sa.Text(), nullable=True),
        sa.Column('visit_log_id',   UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['contract_id'], ['amc_contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],     ondelete='CASCADE'),
    )
    op.create_index('ix_amc_schedules_id',           'amc_service_schedules', ['id'])
    op.create_index('ix_amc_schedules_contract_id',  'amc_service_schedules', ['contract_id'])
    op.create_index('ix_amc_schedules_date',         'amc_service_schedules', ['scheduled_date'])
    op.create_index('ix_amc_schedules_status',       'amc_service_schedules', ['status'])

    # ── service_requests ──────────────────────────────────────────────────────
    op.create_table('service_requests',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('raised_by',        UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('verified_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('complaint_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('asset_id',         UUID(as_uuid=True), nullable=True),
        sa.Column('request_number',   sa.String(20), nullable=False),
        sa.Column('title',            sa.String(255), nullable=False),
        sa.Column('description',      sa.Text(), nullable=True),
        sa.Column('category',         vendor_cat_e, nullable=False),
        sa.Column('priority',         sr_priority_e, nullable=False, server_default='medium'),
        sa.Column('status',           sr_status_e, nullable=False, server_default='open'),
        sa.Column('location',         sa.String(255), nullable=True),
        sa.Column('preferred_date',   sa.Date(), nullable=True),
        sa.Column('scheduled_date',   sa.Date(), nullable=True),
        sa.Column('completed_date',   sa.DateTime(), nullable=True),
        sa.Column('verified_date',    sa.DateTime(), nullable=True),
        sa.Column('sla_due_date',     sa.DateTime(), nullable=True),
        sa.Column('is_overdue',       sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('completion_notes', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('estimated_cost',   sa.Numeric(10,2), nullable=True),
        sa.Column('actual_cost',      sa.Numeric(10,2), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'],   ['vendors.id'],   ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['raised_by'],   ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_service_requests_id',             'service_requests', ['id'])
    op.create_index('ix_service_requests_request_number', 'service_requests', ['request_number'], unique=True)
    op.create_index('ix_service_requests_society_id',     'service_requests', ['society_id'])
    op.create_index('ix_service_requests_vendor_id',      'service_requests', ['vendor_id'])
    op.create_index('ix_service_requests_raised_by',      'service_requests', ['raised_by'])
    op.create_index('ix_service_requests_status',         'service_requests', ['status'])
    op.create_index('ix_service_requests_is_overdue',     'service_requests', ['is_overdue'])

    # ── service_visit_logs ────────────────────────────────────────────────────
    op.create_table('service_visit_logs',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('request_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('contract_id',    UUID(as_uuid=True), nullable=True),
        sa.Column('society_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id',      UUID(as_uuid=True), nullable=True),
        sa.Column('logged_by',      UUID(as_uuid=True), nullable=True),
        sa.Column('visit_date',     sa.Date(), nullable=False),
        sa.Column('check_in_time',  sa.DateTime(), nullable=True),
        sa.Column('check_out_time', sa.DateTime(), nullable=True),
        sa.Column('work_done',      sa.Text(), nullable=True),
        sa.Column('materials_used', sa.Text(), nullable=True),
        sa.Column('next_visit_date',sa.Date(), nullable=True),
        sa.Column('photo_url',      sa.String(500), nullable=True),
        sa.Column('is_satisfactory',sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['request_id'],  ['service_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contract_id'], ['amc_contracts.id'],    ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],        ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'],   ['vendors.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['logged_by'],   ['users.id'],            ondelete='SET NULL'),
    )
    op.create_index('ix_service_visit_logs_id',          'service_visit_logs', ['id'])
    op.create_index('ix_service_visit_logs_request_id',  'service_visit_logs', ['request_id'])
    op.create_index('ix_service_visit_logs_contract_id', 'service_visit_logs', ['contract_id'])
    op.create_index('ix_service_visit_logs_visit_date',  'service_visit_logs', ['visit_date'])

    # ── vendor_invoices ───────────────────────────────────────────────────────
    op.create_table('vendor_invoices',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=False),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id',      UUID(as_uuid=True), nullable=False),
        sa.Column('contract_id',    UUID(as_uuid=True), nullable=True),
        sa.Column('request_id',     UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by',    UUID(as_uuid=True), nullable=True),
        sa.Column('invoice_number', sa.String(50), nullable=False),
        sa.Column('invoice_date',   sa.Date(), nullable=False),
        sa.Column('due_date',       sa.Date(), nullable=True),
        sa.Column('amount',         sa.Numeric(12,2), nullable=False),
        sa.Column('gst_amount',     sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('total_amount',   sa.Numeric(12,2), nullable=False),
        sa.Column('paid_amount',    sa.Numeric(12,2), nullable=False, server_default='0'),
        sa.Column('is_paid',        sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('paid_date',      sa.Date(), nullable=True),
        sa.Column('payment_ref',    sa.String(100), nullable=True),
        sa.Column('description',    sa.Text(), nullable=True),
        sa.Column('doc_url',        sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],   ['societies.id'],        ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'],    ['vendors.id'],          ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contract_id'],  ['amc_contracts.id'],    ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['request_id'],   ['service_requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'],  ['users.id'],            ondelete='SET NULL'),
    )
    op.create_index('ix_vendor_invoices_id',         'vendor_invoices', ['id'])
    op.create_index('ix_vendor_invoices_vendor_id',  'vendor_invoices', ['vendor_id'])
    op.create_index('ix_vendor_invoices_society_id', 'vendor_invoices', ['society_id'])
    op.create_index('ix_vendor_invoices_is_paid',    'vendor_invoices', ['is_paid'])
    op.create_index('ix_vendor_invoices_inv_date',   'vendor_invoices', ['invoice_date'])


def downgrade() -> None:
    for t in ['vendor_invoices','service_visit_logs','service_requests',
              'amc_service_schedules','amc_contracts','vendor_services','vendors']:
        op.drop_table(t)
    for e in ['schedulestatus','servicerequestpriority','servicerequeststatus',
              'servicefrequency','contractstatus','vendorstatus','vendorcategory']:
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
