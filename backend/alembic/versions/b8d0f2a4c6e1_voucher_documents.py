"""Documents filed against a voucher (voucher_documents)

Revision ID: b8d0f2a4c6e1
Revises: a7c9e1b3d5f2
Create Date: 2026-11-19

The supplier's bill, a receipt or a photo of the work, filed against the voucher that booked the expense and opened
from the expenses register. The file is kept in the row, like a payment's screenshot. Additive and idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'b8d0f2a4c6e1'
down_revision = 'a7c9e1b3d5f2'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    if 'voucher_documents' not in sa.inspect(bind).get_table_names():
        op.create_table(
            'voucher_documents',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('voucher_id', UUID(as_uuid=True), sa.ForeignKey('vouchers.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('file_name', sa.String(255), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('data', sa.LargeBinary(), nullable=False),
            sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'),
                      nullable=True),
        )
    existing = {i['name'] for i in sa.inspect(bind).get_indexes('voucher_documents')}
    for name, col in (('ix_voucher_documents_society_id', 'society_id'),
                      ('ix_voucher_documents_voucher_id', 'voucher_id')):
        if name not in existing:
            op.create_index(name, 'voucher_documents', [col])


def downgrade():
    bind = op.get_bind()
    if 'voucher_documents' in sa.inspect(bind).get_table_names():
        for name in ('ix_voucher_documents_voucher_id', 'ix_voucher_documents_society_id'):
            op.drop_index(name, table_name='voucher_documents')
        op.drop_table('voucher_documents')
