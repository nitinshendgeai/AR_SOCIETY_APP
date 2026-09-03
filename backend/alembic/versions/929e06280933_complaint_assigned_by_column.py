"""complaint_assigned_by_column

Revision ID: 929e06280933
Revises: f7a8b9c0d1e2
Create Date: 2026-09-03

Fixes a schema-drift bug: the Complaint model (app/modules/complaint/models/
complaint.py) declares `assigned_by` and `assigned_department` columns, and
ComplaintService.create_complaint()/assign_complaint() write to
`assigned_by` on every complaint creation that auto-assigns to a Manager —
but the original complaint_management_module migration (aab340f2f215) never
created either column. SQLite's test schema is built straight from the
model (Base.metadata.create_all()) so this never surfaced there; on a real
Postgres database (schema from migrations only) every complaint create/
assign that touches `assigned_by` fails with "column does not exist",
surfacing to the app as a 500 on save.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = '929e06280933'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column('complaints', sa.Column('assigned_by', UUID(as_uuid=True), nullable=True))
    op.add_column('complaints', sa.Column('assigned_department', sa.String(50), nullable=True))
    op.create_foreign_key(
        'fk_complaints_assigned_by_users', 'complaints', 'users',
        ['assigned_by'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_complaints_assigned_department', 'complaints', ['assigned_department'])


def downgrade() -> None:
    op.drop_index('ix_complaints_assigned_department', table_name='complaints')
    op.drop_constraint('fk_complaints_assigned_by_users', 'complaints', type_='foreignkey')
    op.drop_column('complaints', 'assigned_department')
    op.drop_column('complaints', 'assigned_by')
