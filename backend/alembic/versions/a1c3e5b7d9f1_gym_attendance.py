"""Gym attendance book: visits, and the screen's form

Revision ID: a1c3e5b7d9f1
Revises: e9b1d3f5a7c9
Create Date: 2026-11-15

gym_visits: one row per member per visit to the gym, ticked in and out by the Gym Trainer, with the member's name and
flat as they were on the day. Only adds a table; nothing existing is changed.

Also registers the "gym_desk" form (Admin, committee, Manager, Gym Trainer). Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = 'a1c3e5b7d9f1'
down_revision = 'e9b1d3f5a7c9'
branch_labels = None
depends_on    = None

_ROLES = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member",
          "Manager", "Gym Trainer")
_FORM = ("gym_desk", "Gym attendance",
         "The gym's attendance book: tick the members of a flat in and out, see who is inside now, and the weekly and monthly report")


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if 'gym_visits' not in tables:
        op.create_table(
            'gym_visits',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('society_id', UUID(as_uuid=True), sa.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('flat_id', UUID(as_uuid=True), sa.ForeignKey('flats.id', ondelete='SET NULL'), nullable=True),
            sa.Column('resident_id', UUID(as_uuid=True), sa.ForeignKey('residents.id', ondelete='SET NULL'), nullable=True),
            sa.Column('member_name', sa.String(255), nullable=False),
            sa.Column('flat_label', sa.String(60), nullable=False),
            sa.Column('member_type', sa.String(20), nullable=True),
            sa.Column('checked_in_at', sa.DateTime(), nullable=False),
            sa.Column('checked_out_at', sa.DateTime(), nullable=True),
            sa.Column('checked_in_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('checked_out_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('closed_late', sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index('ix_gym_visits_society_id', 'gym_visits', ['society_id'])
        op.create_index('ix_gym_visits_flat_id', 'gym_visits', ['flat_id'])
        op.create_index('ix_gym_visits_resident_id', 'gym_visits', ['resident_id'])
        op.create_index('ix_gym_visits_society_in', 'gym_visits', ['society_id', 'checked_in_at'])

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
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'gym_desk')")
    op.execute("DELETE FROM forms WHERE code = 'gym_desk'")
    if 'gym_visits' in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table('gym_visits')
