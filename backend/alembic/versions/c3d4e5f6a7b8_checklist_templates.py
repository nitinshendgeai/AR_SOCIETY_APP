"""checklist_templates

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-04

Tables: checklist_templates, checklist_template_items, duty_checklist_items
Column: duty_assignments.checklist_template_id (nullable FK)

Adds a department-scoped, reusable checklist template system for staff
duties (e.g. "Security Gate Round" for Security, "Room Turnover" for
Housekeeping). Assigning a duty from a template snapshots the template's
items onto duty_checklist_items at that moment, so later template edits
never retroactively change an already-assigned staff member's checklist.

All additions are new, nullable, or new tables, so this migration is safe
to run against a database that already has data — nothing existing changes
behavior until an Admin creates a template and a duty references it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'checklist_templates' not in existing_tables:
        op.create_table(
            'checklist_templates',
            sa.Column('id',          UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at',  sa.DateTime(), nullable=False),
            sa.Column('updated_at',  sa.DateTime(), nullable=False),
            sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('society_id',  UUID(as_uuid=True), nullable=False),
            sa.Column('department',  sa.String(30), nullable=False),
            sa.Column('name',        sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_by',  UUID(as_uuid=True), nullable=True),
            sa.ForeignKeyConstraint(['society_id'], ['societies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_checklist_templates_society_id', 'checklist_templates', ['society_id'])
        op.create_index('ix_checklist_templates_department', 'checklist_templates', ['department'])

    if 'checklist_template_items' not in existing_tables:
        op.create_table(
            'checklist_template_items',
            sa.Column('id',          UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at',  sa.DateTime(), nullable=False),
            sa.Column('updated_at',  sa.DateTime(), nullable=False),
            sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('template_id', UUID(as_uuid=True), nullable=False),
            sa.Column('sequence',    sa.Integer(), nullable=False, server_default='0'),
            sa.Column('title',       sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
            sa.ForeignKeyConstraint(['template_id'], ['checklist_templates.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_checklist_template_items_template_id', 'checklist_template_items', ['template_id'])

    if 'duty_checklist_items' not in existing_tables:
        op.create_table(
            'duty_checklist_items',
            sa.Column('id',                UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at',        sa.DateTime(), nullable=False),
            sa.Column('updated_at',        sa.DateTime(), nullable=False),
            sa.Column('is_active',         sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('duty_id',           UUID(as_uuid=True), nullable=False),
            sa.Column('template_item_id',  UUID(as_uuid=True), nullable=True),
            sa.Column('sequence',          sa.Integer(), nullable=False, server_default='0'),
            sa.Column('title',             sa.String(255), nullable=False),
            sa.Column('description',       sa.Text(), nullable=True),
            sa.Column('is_required',       sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_completed',      sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('completed_at',      sa.DateTime(), nullable=True),
            sa.Column('notes',             sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['duty_id'], ['duty_assignments.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['template_item_id'], ['checklist_template_items.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_duty_checklist_items_duty_id', 'duty_checklist_items', ['duty_id'])

    existing_cols = {c['name'] for c in inspector.get_columns('duty_assignments')} \
        if 'duty_assignments' in existing_tables else set()
    if 'checklist_template_id' not in existing_cols:
        op.add_column('duty_assignments',
            sa.Column('checklist_template_id', UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            'fk_duty_assignments_checklist_template_id', 'duty_assignments',
            'checklist_templates', ['checklist_template_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    op.drop_column('duty_assignments', 'checklist_template_id')
    op.drop_table('duty_checklist_items')
    op.drop_table('checklist_template_items')
    op.drop_table('checklist_templates')
