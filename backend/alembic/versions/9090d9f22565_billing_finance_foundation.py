"""billing_finance_foundation

Revision ID: 9090d9f22565
Revises: c79ac126b2c8
Create Date: 2026-05-26

Tables: financial_periods, maintenance_charge_configs, billing_cycles,
        maintenance_bills, invoice_line_items, payment_receipts,
        due_trackers, penalty_rules
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision      = '9090d9f22565'
down_revision = 'c79ac126b2c8'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    charge_type_e = sa.Enum(
        'maintenance','water','parking','sinking_fund','repair_fund',
        'amenities','penalty','special_assessment','other', name='chargetype'
    )
    bill_status_e = sa.Enum(
        'draft','generated','issued','partially_paid','paid','overdue','cancelled',
        name='billstatus'
    )
    payment_mode_e = sa.Enum(
        'cash','upi','bank_transfer','cheque','online_gateway','neft','rtgs',
        name='paymentmode'
    )
    penalty_calc_e = sa.Enum(
        'flat_amount','percentage','compound_daily', name='penaltycalculationtype'
    )
    cycle_freq_e = sa.Enum(
        'monthly','quarterly','half_yearly','yearly','custom', name='cyclefrequency'
    )

    # ── financial_periods ─────────────────────────────────────────────────────
    op.create_table('financial_periods',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',   UUID(as_uuid=True), nullable=False),
        sa.Column('name',         sa.String(100), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end',   sa.Date(), nullable=False),
        sa.Column('is_closed',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('closed_by',    UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['closed_by'],  ['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_financial_periods_id',           'financial_periods', ['id'])
    op.create_index('ix_financial_periods_society_id',   'financial_periods', ['society_id'])
    op.create_index('ix_financial_periods_period_start', 'financial_periods', ['period_start'])

    # ── maintenance_charge_configs ────────────────────────────────────────────
    op.create_table('maintenance_charge_configs',
        sa.Column('id',                    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',            sa.DateTime(), nullable=False),
        sa.Column('updated_at',            sa.DateTime(), nullable=False),
        sa.Column('is_active',             sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',            UUID(as_uuid=True), nullable=False),
        sa.Column('charge_type',           charge_type_e, nullable=False),
        sa.Column('name',                  sa.String(150), nullable=False),
        sa.Column('description',           sa.Text(), nullable=True),
        sa.Column('default_amount',        sa.Numeric(10,2), nullable=True),
        sa.Column('is_per_sqft',           sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_mandatory',          sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('applicable_flat_types', sa.String(255), nullable=True),
        sa.Column('tax_percent',           sa.Numeric(5,2), nullable=False, server_default='0'),
        sa.Column('effective_from',        sa.Date(), nullable=True),
        sa.Column('effective_to',          sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_charge_configs_id',        'maintenance_charge_configs', ['id'])
    op.create_index('ix_charge_configs_society_id','maintenance_charge_configs', ['society_id'])
    op.create_index('ix_charge_configs_type',      'maintenance_charge_configs', ['charge_type'])

    # ── billing_cycles ────────────────────────────────────────────────────────
    op.create_table('billing_cycles',
        sa.Column('id',                      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',              sa.DateTime(), nullable=False),
        sa.Column('updated_at',              sa.DateTime(), nullable=False),
        sa.Column('is_active',               sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',              UUID(as_uuid=True), nullable=False),
        sa.Column('period_id',               UUID(as_uuid=True), nullable=True),
        sa.Column('created_by',              UUID(as_uuid=True), nullable=True),
        sa.Column('name',                    sa.String(150), nullable=False),
        sa.Column('cycle_start',             sa.Date(), nullable=False),
        sa.Column('cycle_end',               sa.Date(), nullable=False),
        sa.Column('due_date',                sa.Date(), nullable=False),
        sa.Column('frequency',               cycle_freq_e, nullable=False, server_default='monthly'),
        sa.Column('is_finalized',            sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('total_flats_billed',      sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_amount_generated',  sa.Numeric(14,2), nullable=False, server_default='0'),
        sa.Column('total_collected',         sa.Numeric(14,2), nullable=False, server_default='0'),
        sa.Column('notes',                   sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'],        ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['period_id'],  ['financial_periods.id'],ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],            ondelete='SET NULL'),
    )
    op.create_index('ix_billing_cycles_id',        'billing_cycles', ['id'])
    op.create_index('ix_billing_cycles_society_id','billing_cycles', ['society_id'])
    op.create_index('ix_billing_cycles_due_date',  'billing_cycles', ['due_date'])

    # ── maintenance_bills ─────────────────────────────────────────────────────
    op.create_table('maintenance_bills',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',          sa.DateTime(), nullable=False),
        sa.Column('updated_at',          sa.DateTime(), nullable=False),
        sa.Column('is_active',           sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',          UUID(as_uuid=True), nullable=False),
        sa.Column('cycle_id',            UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',             UUID(as_uuid=True), nullable=False),
        sa.Column('resident_id',         UUID(as_uuid=True), nullable=True),
        sa.Column('generated_by',        UUID(as_uuid=True), nullable=True),
        sa.Column('invoice_number',      sa.String(30), nullable=False),
        sa.Column('bill_status',         bill_status_e, nullable=False, server_default='draft'),
        sa.Column('bill_date',           sa.Date(), nullable=False),
        sa.Column('due_date',            sa.Date(), nullable=False),
        sa.Column('subtotal',            sa.Numeric(12,2), nullable=False, server_default='0'),
        sa.Column('tax_amount',          sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('penalty_amount',      sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('discount_amount',     sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('total_amount',        sa.Numeric(12,2), nullable=False, server_default='0'),
        sa.Column('paid_amount',         sa.Numeric(12,2), nullable=False, server_default='0'),
        sa.Column('outstanding',         sa.Numeric(12,2), nullable=False, server_default='0'),
        sa.Column('issued_at',           sa.DateTime(), nullable=True),
        sa.Column('paid_at',             sa.DateTime(), nullable=True),
        sa.Column('cancelled_at',        sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('remarks',             sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cycle_id'],    ['billing_cycles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resident_id'], ['residents.id'],      ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['generated_by'],['users.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_maintenance_bills_id',             'maintenance_bills', ['id'])
    op.create_index('ix_maintenance_bills_invoice_number', 'maintenance_bills', ['invoice_number'], unique=True)
    op.create_index('ix_maintenance_bills_society_id',     'maintenance_bills', ['society_id'])
    op.create_index('ix_maintenance_bills_flat_id',        'maintenance_bills', ['flat_id'])
    op.create_index('ix_maintenance_bills_cycle_id',       'maintenance_bills', ['cycle_id'])
    op.create_index('ix_maintenance_bills_due_date',       'maintenance_bills', ['due_date'])
    op.create_index('ix_maintenance_bills_status',         'maintenance_bills', ['bill_status'])
    op.create_index('ix_maintenance_bills_resident_id',    'maintenance_bills', ['resident_id'])

    # ── invoice_line_items ────────────────────────────────────────────────────
    op.create_table('invoice_line_items',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=False),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('bill_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('charge_type', charge_type_e, nullable=False),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('quantity',    sa.Float(), nullable=False, server_default='1'),
        sa.Column('unit_rate',   sa.Numeric(10,2), nullable=False),
        sa.Column('amount',      sa.Numeric(12,2), nullable=False),
        sa.Column('tax_percent', sa.Numeric(5,2), nullable=False, server_default='0'),
        sa.Column('tax_amount',  sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('total',       sa.Numeric(12,2), nullable=False),
        sa.ForeignKeyConstraint(['bill_id'], ['maintenance_bills.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_invoice_line_items_id',      'invoice_line_items', ['id'])
    op.create_index('ix_invoice_line_items_bill_id', 'invoice_line_items', ['bill_id'])

    # ── payment_receipts ──────────────────────────────────────────────────────
    op.create_table('payment_receipts',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',      sa.DateTime(), nullable=False),
        sa.Column('updated_at',      sa.DateTime(), nullable=False),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',      UUID(as_uuid=True), nullable=False),
        sa.Column('bill_id',         UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',         UUID(as_uuid=True), nullable=True),
        sa.Column('received_by',     UUID(as_uuid=True), nullable=True),
        sa.Column('receipt_number',  sa.String(30), nullable=False),
        sa.Column('payment_date',    sa.Date(), nullable=False),
        sa.Column('amount',          sa.Numeric(12,2), nullable=False),
        sa.Column('payment_mode',    payment_mode_e, nullable=False),
        sa.Column('transaction_ref', sa.String(100), nullable=True),
        sa.Column('cheque_number',   sa.String(50), nullable=True),
        sa.Column('bank_name',       sa.String(100), nullable=True),
        sa.Column('notes',           sa.Text(), nullable=True),
        sa.Column('is_advance',      sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_reversed',     sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reversed_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],  ['societies.id'],      ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bill_id'],     ['maintenance_bills.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],     ['flats.id'],          ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['received_by'], ['users.id'],          ondelete='SET NULL'),
    )
    op.create_index('ix_payment_receipts_id',             'payment_receipts', ['id'])
    op.create_index('ix_payment_receipts_receipt_number', 'payment_receipts', ['receipt_number'], unique=True)
    op.create_index('ix_payment_receipts_society_id',     'payment_receipts', ['society_id'])
    op.create_index('ix_payment_receipts_bill_id',        'payment_receipts', ['bill_id'])
    op.create_index('ix_payment_receipts_flat_id',        'payment_receipts', ['flat_id'])
    op.create_index('ix_payment_receipts_payment_date',   'payment_receipts', ['payment_date'])
    op.create_index('ix_payment_receipts_mode',           'payment_receipts', ['payment_mode'])
    op.create_index('ix_payment_receipts_transaction_ref','payment_receipts', ['transaction_ref'])

    # ── due_trackers ──────────────────────────────────────────────────────────
    op.create_table('due_trackers',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',        sa.DateTime(), nullable=False),
        sa.Column('updated_at',        sa.DateTime(), nullable=False),
        sa.Column('is_active',         sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',        UUID(as_uuid=True), nullable=False),
        sa.Column('flat_id',           UUID(as_uuid=True), nullable=False),
        sa.Column('total_billed',      sa.Numeric(14,2), nullable=False, server_default='0'),
        sa.Column('total_paid',        sa.Numeric(14,2), nullable=False, server_default='0'),
        sa.Column('total_penalty',     sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('total_discount',    sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('outstanding',       sa.Numeric(14,2), nullable=False, server_default='0'),
        sa.Column('advance_balance',   sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('last_payment_date', sa.Date(), nullable=True),
        sa.Column('last_bill_date',    sa.Date(), nullable=True),
        sa.Column('overdue_months',    sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_updated_by',   UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['society_id'],     ['societies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flat_id'],        ['flats.id'],     ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['last_updated_by'],['users.id'],     ondelete='SET NULL'),
    )
    op.create_index('ix_due_trackers_id',         'due_trackers', ['id'])
    op.create_index('ix_due_trackers_flat_id',    'due_trackers', ['flat_id'], unique=True)
    op.create_index('ix_due_trackers_society_id', 'due_trackers', ['society_id'])

    # ── penalty_rules ─────────────────────────────────────────────────────────
    op.create_table('penalty_rules',
        sa.Column('id',                      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('created_at',              sa.DateTime(), nullable=False),
        sa.Column('updated_at',              sa.DateTime(), nullable=False),
        sa.Column('is_active',               sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('society_id',              UUID(as_uuid=True), nullable=False),
        sa.Column('name',                    sa.String(100), nullable=False),
        sa.Column('calc_type',               penalty_calc_e, nullable=False, server_default='percentage'),
        sa.Column('rate',                    sa.Numeric(8,4), nullable=False),
        sa.Column('grace_period_days',       sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_penalty_pct',         sa.Numeric(5,2), nullable=True),
        sa.Column('applies_to_charge_types', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_penalty_rules_id',        'penalty_rules', ['id'])
    op.create_index('ix_penalty_rules_society_id','penalty_rules', ['society_id'])


def downgrade() -> None:
    for t in ['penalty_rules','due_trackers','payment_receipts','invoice_line_items',
              'maintenance_bills','billing_cycles','maintenance_charge_configs','financial_periods']:
        op.drop_table(t)
    for e in ['cyclefrequency','penaltycalculationtype','paymentmode','billstatus','chargetype']:
        sa.Enum(name=e).drop(op.get_bind(), checkfirst=True)
