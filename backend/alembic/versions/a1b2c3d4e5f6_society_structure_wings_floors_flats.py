"""society_structure_wings_floors_flats

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-06-06

Changes:
  ALTER societies: add registration_number, gst_number, pan_number
  ALTER wings: add description column, unique constraints on (society_id, name) and (society_id, code)
  CREATE floors: floor_number, floor_name, wing_id, society_id with unique constraint
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = 'a1b2c3d4e5f6'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on    = None


def upgrade() -> None:

    # ── ALTER societies: legal fields ─────────────────────────────────────────
    op.add_column('societies', sa.Column('registration_number', sa.String(100), nullable=True))
    op.add_column('societies', sa.Column('gst_number',          sa.String(20),  nullable=True))
    op.add_column('societies', sa.Column('pan_number',          sa.String(20),  nullable=True))

    # ── ALTER wings: add description ──────────────────────────────────────────
    op.add_column('wings', sa.Column('description', sa.Text(), nullable=True))

    # Unique constraints on wings (society_id + name), (society_id + code)
    # Use try/except in case they already exist from an earlier partial run
    try:
        op.create_unique_constraint('uq_wing_society_name', 'wings', ['society_id', 'name'])
    except Exception:
        pass
    try:
        op.create_unique_constraint('uq_wing_society_code', 'wings', ['society_id', 'code'])
    except Exception:
        pass

    # ── CREATE floors table ───────────────────────────────────────────────────
    op.create_table(
        'floors',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at',   sa.DateTime(), nullable=False),
        sa.Column('updated_at',   sa.DateTime(), nullable=False),
        sa.Column('is_active',    sa.Boolean(),  nullable=False, server_default='true'),
        sa.Column('floor_number', sa.Integer(),  nullable=False),
        sa.Column('floor_name',   sa.String(50), nullable=True),
        sa.Column('wing_id',
                  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('wings.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('society_id',
                  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('societies.id', ondelete='CASCADE'),
                  nullable=False, index=True),
    )
    op.create_unique_constraint(
        'uq_floor_wing_number', 'floors', ['wing_id', 'floor_number']
    )
    op.create_index('ix_floors_id',         'floors', ['id'])
    op.create_index('ix_floors_wing_id',    'floors', ['wing_id'])
    op.create_index('ix_floors_society_id', 'floors', ['society_id'])


def downgrade() -> None:
    op.drop_table('floors')

    op.drop_constraint('uq_wing_society_code', 'wings', type_='unique')
    op.drop_constraint('uq_wing_society_name', 'wings', type_='unique')
    op.drop_column('wings', 'description')

    op.drop_column('societies', 'pan_number')
    op.drop_column('societies', 'gst_number')
    op.drop_column('societies', 'registration_number')
