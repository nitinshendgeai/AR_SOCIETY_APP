"""Society accounts: chart of accounts, vouchers and ledgers

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-09-29

Adds the double-entry books (see app/modules/accounts): account_groups,
accounts (ledgers), vouchers and voucher_entries; vendor_invoices gets the
expense head it's booked to; and the "accounts" screen is registered and
granted to Society Admin, the committee and the Manager. Each society's
standard chart is created the first time its books are opened, so nothing
is seeded here. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'f3c4d5e6f7a8'
down_revision = 'f2b3c4d5e6f7'
branch_labels = None
depends_on    = None

FORM_CODE = "accounts"
FORM_NAME = "Accounts"
FORM_DESC = "Chart of accounts, vouchers, cash and bank books, and ledgers"
_GRANTED_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member", "Manager",
)


def _base_columns():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    ]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'account_groups' not in tables:
        op.create_table(
            'account_groups', *_base_columns(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('nature', sa.String(20), nullable=False),
            sa.Column('system_key', sa.String(50), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
            sa.UniqueConstraint('society_id', 'name', name='uq_account_groups_society_name'),
        )
        op.create_index('ix_account_groups_society_id', 'account_groups', ['society_id'])

    if 'accounts' not in tables:
        op.create_table(
            'accounts', *_base_columns(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('group_id', UUID(as_uuid=True), sa.ForeignKey('account_groups.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('code', sa.String(20), nullable=True),
            sa.Column('name', sa.String(150), nullable=False),
            sa.Column('system_key', sa.String(50), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('opening_balance', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('opening_type', sa.String(2), nullable=False, server_default='dr'),
            sa.Column('is_cash', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_bank', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_default_bank', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('bank_name', sa.String(100), nullable=True),
            sa.Column('bank_account_number', sa.String(40), nullable=True),
            sa.Column('bank_ifsc', sa.String(20), nullable=True),
            sa.Column('bank_branch', sa.String(100), nullable=True),
            sa.UniqueConstraint('society_id', 'name', name='uq_accounts_society_name'),
        )
        op.create_index('ix_accounts_society_id', 'accounts', ['society_id'])
        op.create_index('ix_accounts_group_id', 'accounts', ['group_id'])
        op.create_index('ix_accounts_system_key', 'accounts', ['system_key'])

    if 'vouchers' not in tables:
        op.create_table(
            'vouchers', *_base_columns(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('voucher_type', sa.String(20), nullable=False),
            sa.Column('voucher_number', sa.String(40), nullable=False),
            sa.Column('voucher_date', sa.Date(), nullable=False),
            sa.Column('fiscal_year', sa.String(7), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('narration', sa.Text(), nullable=True),
            sa.Column('reference', sa.String(100), nullable=True),
            sa.Column('source_type', sa.String(40), nullable=True),
            sa.Column('source_id', UUID(as_uuid=True), nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('is_cancelled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
            sa.Column('cancelled_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('cancel_reason', sa.Text(), nullable=True),
            sa.UniqueConstraint('society_id', 'voucher_number', name='uq_vouchers_society_number'),
        )
        for col in ('society_id', 'voucher_type', 'voucher_date', 'fiscal_year', 'source_type', 'source_id',
                    'is_cancelled'):
            op.create_index(f'ix_vouchers_{col}', 'vouchers', [col])

    if 'voucher_entries' not in tables:
        op.create_table(
            'voucher_entries', *_base_columns(),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('line_no', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('debit', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('credit', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='SET NULL'), nullable=True),
            sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='SET NULL'), nullable=True),
            sa.Column('narration', sa.Text(), nullable=True),
        )
        for col in ('voucher_id', 'account_id', 'flat_id', 'vendor_id'):
            op.create_index(f'ix_voucher_entries_{col}', 'voucher_entries', [col])

    if 'expense_account_id' not in {c['name'] for c in inspector.get_columns('vendor_invoices')}:
        op.add_column('vendor_invoices', sa.Column('expense_account_id', UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_vendor_invoices_expense_account', 'vendor_invoices', 'accounts',
                              ['expense_account_id'], ['id'], ondelete='SET NULL')

    # The Accounts screen, granted like the other finance screens.
    now = datetime.utcnow()
    row = bind.execute(sa.text("SELECT id FROM forms WHERE code = :c"), {"c": FORM_CODE}).first()
    if row:
        form_id = row[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(sa.text("""
            INSERT INTO forms (id, code, name, description, created_at, updated_at, is_active)
            VALUES (:id, :code, :name, :desc, :now, :now, true)
        """), {"id": form_id, "code": FORM_CODE, "name": FORM_NAME, "desc": FORM_DESC, "now": now})
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
    op.drop_constraint('fk_vendor_invoices_expense_account', 'vendor_invoices', type_='foreignkey')
    op.drop_column('vendor_invoices', 'expense_account_id')
    op.drop_table('voucher_entries')
    op.drop_table('vouchers')
    op.drop_table('accounts')
    op.drop_table('account_groups')
