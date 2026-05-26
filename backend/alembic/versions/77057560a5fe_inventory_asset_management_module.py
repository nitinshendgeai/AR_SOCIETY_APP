"""inventory_asset_management_module

Revision ID: 77057560a5fe
Revises: f0812cc4eed1
Create Date: 2026-05-23

Tables: inventory_categories, inventory_items, inventory_stock,
        inventory_transactions, inventory_issues, inventory_returns,
        assets, asset_maintenance, asset_amc, asset_usage_logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '77057560a5fe'
down_revision = 'f0812cc4eed1'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    item_cat  = sa.Enum('cleaning','electrical','plumbing','safety','tools','uniforms','stationery','housekeeping','gardening','other', name='itemcategory')
    unit_type = sa.Enum('piece','kg','litre','meter','box','pack','roll','set','pair', name='unittype')
    txn_type  = sa.Enum('stock_in','stock_out','transfer','return','adjustment','consumption', name='transactiontype')
    issue_st  = sa.Enum('issued','partially_returned','returned','consumed', name='issuestatus')
    asset_cat = sa.Enum('lift','cctv','pump','generator','biometric','fire_safety','electrical','hvac','vehicle','furniture','it_equipment','other', name='assetcategory')
    asset_st  = sa.Enum('active','under_maintenance','retired','disposed','lost', name='assetstatus')
    maint_t   = sa.Enum('preventive','corrective','emergency','amc_service', name='maintenancetype')
    maint_st  = sa.Enum('scheduled','in_progress','completed','cancelled', name='maintenancestatus')

    # ── inventory_categories ──────────────────────────────────────────────────
    op.create_table('inventory_categories',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('name',        sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_inventory_categories_id',        'inventory_categories', ['id'])
    op.create_index('ix_inventory_categories_society_id','inventory_categories', ['society_id'])

    # ── inventory_items ───────────────────────────────────────────────────────
    op.create_table('inventory_items',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('category_id',      UUID(as_uuid=True), nullable=True),
        sa.Column('item_code',        sa.String(30), nullable=False),
        sa.Column('name',             sa.String(255), nullable=False),
        sa.Column('description',      sa.Text(), nullable=True),
        sa.Column('category',         item_cat, nullable=False),
        sa.Column('unit_type',        unit_type, nullable=False, server_default='piece'),
        sa.Column('storage_location', sa.String(255), nullable=True),
        sa.Column('minimum_stock',    sa.Float(), nullable=False, server_default='0'),
        sa.Column('unit_cost',        sa.Numeric(10,2), nullable=True),
        sa.Column('image_url',        sa.String(500), nullable=True),
        sa.Column('vendor_name',      sa.String(255), nullable=True),
        sa.Column('vendor_contact',   sa.String(100), nullable=True),
        sa.Column('remarks',          sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['inventory_categories.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_inventory_items_id',        'inventory_items', ['id'])
    op.create_index('ix_inventory_items_code',      'inventory_items', ['item_code'], unique=True)
    op.create_index('ix_inventory_items_society_id','inventory_items', ['society_id'])
    op.create_index('ix_inventory_items_category',  'inventory_items', ['category'])
    op.create_index('ix_inventory_items_category_id','inventory_items', ['category_id'])

    # ── inventory_stock ───────────────────────────────────────────────────────
    op.create_table('inventory_stock',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('item_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('current_quantity', sa.Float(), nullable=False, server_default='0'),
        sa.Column('last_updated_by',  UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['item_id'],         ['inventory_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'],      ['societies.id'],       ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['last_updated_by'], ['users.id'],           ondelete='SET NULL'),
    )
    op.create_index('ix_inventory_stock_id',     'inventory_stock', ['id'])
    op.create_index('ix_inventory_stock_item_id','inventory_stock', ['item_id'], unique=True)

    # ── inventory_transactions ────────────────────────────────────────────────
    op.create_table('inventory_transactions',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('item_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_type', txn_type, nullable=False),
        sa.Column('quantity',         sa.Float(), nullable=False),
        sa.Column('quantity_before',  sa.Float(), nullable=False),
        sa.Column('quantity_after',   sa.Float(), nullable=False),
        sa.Column('unit_cost',        sa.Numeric(10,2), nullable=True),
        sa.Column('total_cost',       sa.Numeric(12,2), nullable=True),
        sa.Column('reference_id',     sa.String(100), nullable=True),
        sa.Column('notes',            sa.Text(), nullable=True),
        sa.Column('performed_by',     UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],   ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'],      ['inventory_items.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'], ['users.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_inventory_transactions_id',     'inventory_transactions', ['id'])
    op.create_index('ix_inventory_transactions_item_id','inventory_transactions', ['item_id'])
    op.create_index('ix_inventory_transactions_type',   'inventory_transactions', ['transaction_type'])

    # ── inventory_issues ──────────────────────────────────────────────────────
    op.create_table('inventory_issues',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',          sa.DateTime(), nullable=False),
        sa.Column('updated_at',          sa.DateTime(), nullable=False),
        sa.Column('is_active',           sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('item_id',             UUID(as_uuid=True), nullable=False),
        sa.Column('issued_to_user',      UUID(as_uuid=True), nullable=True),
        sa.Column('issued_to_staff',     UUID(as_uuid=True), nullable=True),
        sa.Column('issued_by',           UUID(as_uuid=True), nullable=True),
        sa.Column('complaint_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('task_id',             UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_issued',     sa.Float(), nullable=False),
        sa.Column('quantity_returned',   sa.Float(), nullable=False, server_default='0'),
        sa.Column('status',              issue_st, nullable=False, server_default='issued'),
        sa.Column('purpose',             sa.Text(), nullable=True),
        sa.Column('expected_return_date',sa.Date(), nullable=True),
        sa.Column('actual_return_date',  sa.Date(), nullable=True),
        sa.Column('notes',               sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],     ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'],        ['inventory_items.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['issued_to_user'], ['users.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['issued_by'],      ['users.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_inventory_issues_id',            'inventory_issues', ['id'])
    op.create_index('ix_inventory_issues_item_id',       'inventory_issues', ['item_id'])
    op.create_index('ix_inventory_issues_society_id',    'inventory_issues', ['society_id'])
    op.create_index('ix_inventory_issues_issued_to_user','inventory_issues', ['issued_to_user'])
    op.create_index('ix_inventory_issues_status',        'inventory_issues', ['status'])

    # ── inventory_returns ─────────────────────────────────────────────────────
    op.create_table('inventory_returns',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('issue_id',    UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
        sa.Column('quantity',    sa.Float(), nullable=False),
        sa.Column('condition',   sa.String(50), nullable=True),
        sa.Column('returned_by', UUID(as_uuid=True), nullable=True),
        sa.Column('received_by', UUID(as_uuid=True), nullable=True),
        sa.Column('notes',       sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['issue_id'],    ['inventory_issues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],        ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['returned_by'], ['users.id'],            ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['received_by'], ['users.id'],            ondelete='SET NULL'),
    )
    op.create_index('ix_inventory_returns_id',       'inventory_returns', ['id'])
    op.create_index('ix_inventory_returns_issue_id', 'inventory_returns', ['issue_id'])

    # ── assets ────────────────────────────────────────────────────────────────
    op.create_table('assets',
        sa.Column('id',                 UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',         sa.DateTime(), nullable=False),
        sa.Column('updated_at',         sa.DateTime(), nullable=False),
        sa.Column('is_active',          sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('asset_code',         sa.String(30), nullable=False),
        sa.Column('name',               sa.String(255), nullable=False),
        sa.Column('asset_category',     asset_cat, nullable=False),
        sa.Column('description',        sa.Text(), nullable=True),
        sa.Column('location',           sa.String(255), nullable=True),
        sa.Column('status',             asset_st, nullable=False, server_default='active'),
        sa.Column('purchase_date',      sa.Date(), nullable=True),
        sa.Column('purchase_cost',      sa.Numeric(12,2), nullable=True),
        sa.Column('vendor_name',        sa.String(255), nullable=True),
        sa.Column('vendor_contact',     sa.String(100), nullable=True),
        sa.Column('invoice_number',     sa.String(100), nullable=True),
        sa.Column('warranty_expiry',    sa.Date(), nullable=True),
        sa.Column('expected_life_years',sa.Integer(), nullable=True),
        sa.Column('serial_number',      sa.String(100), nullable=True),
        sa.Column('model_number',       sa.String(100), nullable=True),
        sa.Column('image_url',          sa.String(500), nullable=True),
        sa.Column('assigned_to_staff',  UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_to_user',   UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_at',        sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],       ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_to_user'], ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_assets_id',          'assets', ['id'])
    op.create_index('ix_assets_code',        'assets', ['asset_code'], unique=True)
    op.create_index('ix_assets_society_id',  'assets', ['society_id'])
    op.create_index('ix_assets_category',    'assets', ['asset_category'])
    op.create_index('ix_assets_status',      'assets', ['status'])
    op.create_index('ix_assets_serial',      'assets', ['serial_number'])

    # ── asset_maintenance ─────────────────────────────────────────────────────
    op.create_table('asset_maintenance',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asset_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',       UUID(as_uuid=True), nullable=False),
        sa.Column('maintenance_type', maint_t, nullable=False),
        sa.Column('status',           maint_st, nullable=False, server_default='scheduled'),
        sa.Column('scheduled_date',   sa.Date(), nullable=False),
        sa.Column('completed_date',   sa.Date(), nullable=True),
        sa.Column('vendor_name',      sa.String(255), nullable=True),
        sa.Column('vendor_contact',   sa.String(100), nullable=True),
        sa.Column('cost',             sa.Numeric(10,2), nullable=True),
        sa.Column('description',      sa.Text(), nullable=True),
        sa.Column('findings',         sa.Text(), nullable=True),
        sa.Column('next_due_date',    sa.Date(), nullable=True),
        sa.Column('performed_by',     UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'],    ['assets.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by'],['users.id'],    ondelete='SET NULL'),
    )
    op.create_index('ix_asset_maintenance_id',       'asset_maintenance', ['id'])
    op.create_index('ix_asset_maintenance_asset_id', 'asset_maintenance', ['asset_id'])
    op.create_index('ix_asset_maintenance_type',     'asset_maintenance', ['maintenance_type'])
    op.create_index('ix_asset_maintenance_status',   'asset_maintenance', ['status'])

    # ── asset_amc ─────────────────────────────────────────────────────────────
    op.create_table('asset_amc',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',      sa.DateTime(), nullable=False),
        sa.Column('updated_at',      sa.DateTime(), nullable=False),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asset_id',        UUID(as_uuid=True), nullable=False),
        sa.Column('society_id',      UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_name',     sa.String(255), nullable=False),
        sa.Column('vendor_contact',  sa.String(100), nullable=True),
        sa.Column('contract_number', sa.String(100), nullable=True),
        sa.Column('start_date',      sa.Date(), nullable=False),
        sa.Column('end_date',        sa.Date(), nullable=False),
        sa.Column('annual_cost',     sa.Numeric(10,2), nullable=True),
        sa.Column('coverage',        sa.Text(), nullable=True),
        sa.Column('is_comprehensive',sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_renew',      sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('document_url',    sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'],   ['assets.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],ondelete='CASCADE'),
    )
    op.create_index('ix_asset_amc_id',       'asset_amc', ['id'])
    op.create_index('ix_asset_amc_asset_id', 'asset_amc', ['asset_id'])
    op.create_index('ix_asset_amc_end_date', 'asset_amc', ['end_date'])

    # ── asset_usage_logs ──────────────────────────────────────────────────────
    op.create_table('asset_usage_logs',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asset_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('society_id', UUID(as_uuid=True), nullable=False),
        sa.Column('logged_by',  UUID(as_uuid=True), nullable=True),
        sa.Column('action',     sa.String(100), nullable=False),
        sa.Column('notes',      sa.Text(), nullable=True),
        sa.Column('cost',       sa.Numeric(10,2), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'],  ['assets.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['society_id'],['societies.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['logged_by'], ['users.id'],    ondelete='SET NULL'),
    )
    op.create_index('ix_asset_usage_logs_id',       'asset_usage_logs', ['id'])
    op.create_index('ix_asset_usage_logs_asset_id', 'asset_usage_logs', ['asset_id'])


def downgrade() -> None:
    op.drop_table('asset_usage_logs')
    op.drop_table('asset_amc')
    op.drop_table('asset_maintenance')
    op.drop_table('assets')
    op.drop_table('inventory_returns')
    op.drop_table('inventory_issues')
    op.drop_table('inventory_transactions')
    op.drop_table('inventory_stock')
    op.drop_table('inventory_items')
    op.drop_table('inventory_categories')
    for e in ['maintenancestatus','maintenancetype','assetstatus','assetcategory',
              'issuestatus','transactiontype','unittype','itemcategory']:
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
