"""Duty plans (several staff, several days) and paper-sheet entry

Revision ID: fe4f5a6b7c8d
Revises: fd3e4f5a6b7c
Create Date: 2026-10-04

- duty_assignments.series_id: duties made together by one plan.
- duty_assignments.completed_by / completion_source: who completed the duty and
  whether from the app or from a printed sheet entered by a supervisor.
- duty_checklist_items.completed_by / entered_from_paper: the same, per item.
Idempotent.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'fe4f5a6b7c8d'
down_revision = 'fd3e4f5a6b7c'
branch_labels = None
depends_on    = None


def _cols(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table):
    return {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    duties = _cols('duty_assignments')
    if 'series_id' not in duties:
        op.add_column('duty_assignments', sa.Column('series_id', UUID(as_uuid=True), nullable=True))
    if 'completed_by' not in duties:
        op.add_column('duty_assignments', sa.Column(
            'completed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    if 'completion_source' not in duties:
        op.add_column('duty_assignments', sa.Column('completion_source', sa.String(10), nullable=True))
    existing = _indexes('duty_assignments')
    for name, col in (('ix_duty_assignments_series_id', 'series_id'),
                      ('ix_duty_assignments_completed_by', 'completed_by')):
        if name not in existing:
            op.create_index(name, 'duty_assignments', [col])

    items = _cols('duty_checklist_items')
    if 'completed_by' not in items:
        op.add_column('duty_checklist_items', sa.Column(
            'completed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    if 'entered_from_paper' not in items:
        op.add_column('duty_checklist_items', sa.Column(
            'entered_from_paper', sa.Boolean(), nullable=False, server_default=sa.false()))
    if 'ix_duty_checklist_items_completed_by' not in _indexes('duty_checklist_items'):
        op.create_index('ix_duty_checklist_items_completed_by', 'duty_checklist_items', ['completed_by'])


def downgrade():
    for name, table in (('ix_duty_checklist_items_completed_by', 'duty_checklist_items'),
                        ('ix_duty_assignments_completed_by', 'duty_assignments'),
                        ('ix_duty_assignments_series_id', 'duty_assignments')):
        if name in _indexes(table):
            op.drop_index(name, table_name=table)
    for table, cols in (('duty_checklist_items', ('entered_from_paper', 'completed_by')),
                        ('duty_assignments', ('completion_source', 'completed_by', 'series_id'))):
        present = _cols(table)
        for c in cols:
            if c in present:
                op.drop_column(table, c)
