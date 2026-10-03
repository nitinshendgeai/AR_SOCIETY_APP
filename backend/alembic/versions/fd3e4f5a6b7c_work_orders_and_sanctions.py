"""Work orders, quotations and sanctions as the model bye-laws require

Revision ID: fd3e4f5a6b7c
Revises: fc2d3e4f5a6b
Create Date: 2026-10-03

- procurement_settings: the committee's spending limit and the tender limit
  fixed by the general body (bye-law 157); blank means the bye-law slab.
- work_orders: a one-time work given to a vendor, from quotations to closure.
- vendor_quotations: quotations / tenders for a work order or an annual contract.
- Sanction columns on work_orders and amc_contracts: resolution numbers and
  dates, tenders opened on, reason for not taking the lowest, no-interest
  declaration.
- vendor_invoices.work_order_id: a vendor's bill against a work order.
- The "vendors" screen (Vendors & Work) for Admin, committee and Manager.
Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision      = 'fd3e4f5a6b7c'
down_revision = 'fc2d3e4f5a6b'
branch_labels = None
depends_on    = None

FORM_CODE = "vendors"
_GRANTED_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member", "Manager",
)


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _base_cols():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def _sanction_cols(level):
    return [
        sa.Column('sanctioned_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('sanction_level', level, nullable=True),
        sa.Column('committee_resolution_no', sa.String(50), nullable=True),
        sa.Column('committee_meeting_date', sa.Date(), nullable=True),
        sa.Column('gb_resolution_no', sa.String(50), nullable=True),
        sa.Column('gb_meeting_date', sa.Date(), nullable=True),
        sa.Column('tenders_opened_on', sa.Date(), nullable=True),
        sa.Column('selection_reason', sa.Text(), nullable=True),
        sa.Column('no_interest_declared', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sanctioned_at', sa.DateTime(), nullable=True),
        sa.Column('sanctioned_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    ]


def upgrade():
    bind = op.get_bind()
    level = ENUM('committee', 'general_body', name='sanctionlevel', create_type=False)
    level.create(bind, checkfirst=True)
    wo_status = ENUM('draft', 'sanctioned', 'issued', 'completed', 'closed', 'cancelled',
                     name='workorderstatus', create_type=False)
    wo_status.create(bind, checkfirst=True)
    category = ENUM(name='vendorcategory', create_type=False)

    tables = _tables()
    if 'procurement_settings' not in tables:
        op.create_table(
            'procurement_settings', *_base_cols(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'),
                      nullable=False, unique=True),
            sa.Column('committee_limit', sa.Numeric(12, 2), nullable=True),
            sa.Column('tender_limit', sa.Numeric(12, 2), nullable=True),
            sa.Column('min_quotations', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('gb_resolution_no', sa.String(50), nullable=True),
            sa.Column('gb_meeting_date', sa.Date(), nullable=True),
        )
        op.create_index('ix_procurement_settings_society_id', 'procurement_settings', ['society_id'], unique=True)

    if 'work_orders' not in tables:
        op.create_table(
            'work_orders', *_base_cols(), *_sanction_cols(level),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='SET NULL'), nullable=True),
            sa.Column('service_request_id', UUID(as_uuid=True),
                      sa.ForeignKey('service_requests.id', ondelete='SET NULL'), nullable=True),
            sa.Column('complaint_id', UUID(as_uuid=True), sa.ForeignKey('complaints.id', ondelete='SET NULL'), nullable=True),
            sa.Column('asset_id', UUID(as_uuid=True), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
            sa.Column('expense_account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='SET NULL'),
                      nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('completed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('cancelled_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('wo_number', sa.String(30), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('scope_of_work', sa.Text(), nullable=True),
            sa.Column('location', sa.String(255), nullable=True),
            sa.Column('category', category, nullable=False),
            sa.Column('estimated_cost', sa.Numeric(12, 2), nullable=True),
            sa.Column('status', wo_status, nullable=False, server_default='draft'),
            sa.Column('start_date', sa.Date(), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('payment_terms', sa.Text(), nullable=True),
            sa.Column('advance_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('retention_pct', sa.Numeric(5, 2), nullable=False, server_default='0'),
            sa.Column('defect_liability_months', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('issued_on', sa.Date(), nullable=True),
            sa.Column('completed_on', sa.Date(), nullable=True),
            sa.Column('completion_notes', sa.Text(), nullable=True),
            sa.Column('certificate_ref', sa.String(100), nullable=True),
            sa.Column('retention_released_on', sa.Date(), nullable=True),
            sa.Column('closed_on', sa.Date(), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
            sa.Column('cancel_reason', sa.Text(), nullable=True),
            sa.UniqueConstraint('society_id', 'wo_number', name='uq_work_order_society_number'),
        )
        for col in ('society_id', 'vendor_id', 'service_request_id', 'complaint_id', 'asset_id',
                    'wo_number', 'category', 'status'):
            op.create_index(f'ix_work_orders_{col}', 'work_orders', [col])

    if 'vendor_quotations' not in tables:
        op.create_table(
            'vendor_quotations', *_base_cols(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('work_order_id', UUID(as_uuid=True), sa.ForeignKey('work_orders.id', ondelete='CASCADE'), nullable=True),
            sa.Column('contract_id', UUID(as_uuid=True), sa.ForeignKey('amc_contracts.id', ondelete='CASCADE'), nullable=True),
            sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
            sa.Column('received_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('quotation_ref', sa.String(50), nullable=True),
            sa.Column('quotation_date', sa.Date(), nullable=False),
            sa.Column('valid_until', sa.Date(), nullable=True),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('gst_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('remarks', sa.Text(), nullable=True),
            sa.Column('doc_url', sa.String(500), nullable=True),
            sa.Column('is_selected', sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        for col in ('society_id', 'work_order_id', 'contract_id', 'vendor_id'):
            op.create_index(f'ix_vendor_quotations_{col}', 'vendor_quotations', [col])

    have = _cols('amc_contracts')
    for col in _sanction_cols(level):
        if col.name not in have:
            op.add_column('amc_contracts', col)

    if 'work_order_id' not in _cols('vendor_invoices'):
        op.add_column('vendor_invoices', sa.Column('work_order_id', UUID(as_uuid=True),
                                                   sa.ForeignKey('work_orders.id', ondelete='SET NULL'), nullable=True))
        op.create_index('ix_vendor_invoices_work_order_id', 'vendor_invoices', ['work_order_id'])

    now = datetime.utcnow()
    row = bind.execute(sa.text("SELECT id FROM forms WHERE code = :c"), {"c": FORM_CODE}).first()
    if row:
        form_id = row[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(sa.text("""
            INSERT INTO forms (id, code, name, description, created_at, updated_at, is_active)
            VALUES (:id, :code, 'Vendors & Work',
                    'Vendor master, quotations, work orders and annual contracts, sanctioned as the bye-laws require',
                    :now, :now, true)
        """), {"id": form_id, "code": FORM_CODE, "now": now})
    missing = bind.execute(sa.text("""
        SELECT r.id FROM roles r
        WHERE r.name = ANY(:names)
          AND NOT EXISTS (SELECT 1 FROM role_forms x WHERE x.role_id = r.id AND x.form_id = :form_id)
    """), {"names": list(_GRANTED_ROLES), "form_id": form_id}).fetchall()
    for (role_id,) in missing:
        bind.execute(sa.text("""
            INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
            VALUES (:id, :role_id, :form_id, :now, :now, true)
        """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    op.execute(f"DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = '{FORM_CODE}')")
    op.execute(f"DELETE FROM forms WHERE code = '{FORM_CODE}'")
    op.drop_index('ix_vendor_invoices_work_order_id', table_name='vendor_invoices')
    op.drop_column('vendor_invoices', 'work_order_id')
    for col in ('sanctioned_by', 'sanctioned_at', 'no_interest_declared', 'selection_reason', 'tenders_opened_on',
                'gb_meeting_date', 'gb_resolution_no', 'committee_meeting_date', 'committee_resolution_no',
                'sanction_level', 'sanctioned_amount'):
        op.drop_column('amc_contracts', col)
    op.drop_table('vendor_quotations')
    op.drop_table('work_orders')
    op.drop_table('procurement_settings')
    ENUM(name='workorderstatus').drop(op.get_bind(), checkfirst=True)
    ENUM(name='sanctionlevel').drop(op.get_bind(), checkfirst=True)
