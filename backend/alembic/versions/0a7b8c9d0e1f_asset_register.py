"""Asset register: service schedule columns and more categories

Revision ID: 0a7b8c9d0e1f
Revises: ff5a6b7c8d9e
Create Date: 2026-10-07

Adds the servicing columns to ``assets`` (interval, last serviced, next due) and the categories a
society asks for (air conditioners, water tanks, treatment plants, solar, gym equipment, intercom,
garden equipment). Idempotent.
"""
import sqlalchemy as sa
from alembic import op

revision      = '0a7b8c9d0e1f'
down_revision = 'ff5a6b7c8d9e'
branch_labels = None
depends_on    = None

NEW_CATEGORIES = ('air_conditioner', 'water_tank', 'water_treatment', 'solar',
                  'gym_equipment', 'intercom', 'garden_equipment')


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('assets')}
    if 'service_interval_months' not in existing:
        op.add_column('assets', sa.Column('service_interval_months', sa.Integer(), nullable=True))
    if 'last_serviced_on' not in existing:
        op.add_column('assets', sa.Column('last_serviced_on', sa.Date(), nullable=True))
    if 'next_service_due' not in existing:
        op.add_column('assets', sa.Column('next_service_due', sa.Date(), nullable=True))
    if 'ix_assets_next_service_due' not in {i['name'] for i in inspector.get_indexes('assets')}:
        op.create_index('ix_assets_next_service_due', 'assets', ['next_service_due'])

    if bind.dialect.name == 'postgresql':
        # ALTER TYPE ... ADD VALUE can't run inside a transaction on older servers
        with op.get_context().autocommit_block():
            for value in NEW_CATEGORIES:
                op.execute(f"ALTER TYPE assetcategory ADD VALUE IF NOT EXISTS '{value}'")


def downgrade():
    # Postgres can't drop enum values, so the categories stay; only the columns go.
    op.drop_index('ix_assets_next_service_due', table_name='assets')
    for col in ('next_service_due', 'last_serviced_on', 'service_interval_months'):
        op.drop_column('assets', col)
