"""Monthly lights check: light points, their check history, and the screen's form

Revision ID: d7a9c1e3f5b7
Revises: b8d0f2a4c6e8
Create Date: 2026-11-12

light_points: one row per common light that has been checked (a tube light on a floor or its staircase, or a spot light
in a flat's hall, bedroom or kitchen), with how it was last found. light_check_entries: every check and replacement,
stamped with the date, time and person.

Also registers the "lights_check" form (Admin, committee, Manager, Technical Supervisor, Technical Staff). Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'd7a9c1e3f5b7'
down_revision = 'b8d0f2a4c6e8'
branch_labels = None
depends_on    = None

_ROLES = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member",
          "Manager", "Technical Supervisor", "Technical Staff")
_FORM = ("lights_check", "Lights check",
         "Monthly check of the common tube lights on each floor and the spot lights in each flat; replace what is not working")


def _mixin():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if 'light_points' not in tables:
        op.create_table(
            'light_points', *_mixin(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('wing_id', UUID(as_uuid=True), sa.ForeignKey('wings.id', ondelete='CASCADE'), nullable=False),
            sa.Column('floor_number', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(10), nullable=False),
            sa.Column('location', sa.String(20), nullable=False),
            sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='CASCADE'), nullable=True),
            sa.Column('point_key', sa.String(160), nullable=False),
            sa.Column('status', sa.String(12), nullable=False),
            sa.Column('last_checked_at', sa.DateTime(), nullable=False),
            sa.Column('last_checked_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('not_working_since', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('point_key', name='uq_light_points_point_key'),
        )
        op.create_index('ix_light_points_society_id', 'light_points', ['society_id'])
        op.create_index('ix_light_points_floor', 'light_points', ['wing_id', 'floor_number', 'kind'])
    if 'light_check_entries' not in tables:
        op.create_table(
            'light_check_entries', *_mixin(),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('point_id', UUID(as_uuid=True), sa.ForeignKey('light_points.id', ondelete='CASCADE'), nullable=False),
            sa.Column('event', sa.String(10), nullable=False),
            sa.Column('status', sa.String(12), nullable=False),
            sa.Column('at', sa.DateTime(), nullable=False),
            sa.Column('by_user', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('inventory_items.id', ondelete='SET NULL'), nullable=True),
            sa.Column('quantity', sa.Float(), nullable=True),
        )
        op.create_index('ix_light_check_entries_society_id', 'light_check_entries', ['society_id'])
        op.create_index('ix_light_check_entries_point_id', 'light_check_entries', ['point_id'])
        op.create_index('ix_light_check_entries_at', 'light_check_entries', ['at'])

    now = datetime.utcnow()
    code, name, description = _FORM
    row = bind.execute(sa.text("SELECT id FROM forms WHERE code = :c"), {"c": code}).first()
    if row:
        form_id = row[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(sa.text("""
            INSERT INTO forms (id, code, name, description, created_at, updated_at, is_active)
            VALUES (:id, :code, :name, :description, :now, :now, true)
        """), {"id": form_id, "code": code, "name": name, "description": description, "now": now})
    missing = bind.execute(sa.text("""
        SELECT r.id FROM roles r
        WHERE r.name = ANY(:names)
          AND NOT EXISTS (SELECT 1 FROM role_forms x WHERE x.role_id = r.id AND x.form_id = :form_id)
    """), {"names": list(_ROLES), "form_id": form_id}).fetchall()
    for (role_id,) in missing:
        bind.execute(sa.text("""
            INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
            VALUES (:id, :role_id, :form_id, :now, :now, true)
        """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'lights_check')")
    op.execute("DELETE FROM forms WHERE code = 'lights_check'")
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'light_check_entries' in tables:
        op.drop_table('light_check_entries')
    if 'light_points' in tables:
        op.drop_table('light_points')
