"""Defaulters screen

Revision ID: f5e6f7a8b9c0
Revises: f4d5e6f7a8b9
Create Date: 2026-10-02

Registers the "defaulters" screen (members' dues aged, the list of
defaulters and reminders) and grants it to Society Admin, the committee and
the Manager, like the other finance screens. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = 'f5e6f7a8b9c0'
down_revision = 'f4d5e6f7a8b9'
branch_labels = None
depends_on    = None

FORM_CODE = "defaulters"
_GRANTED_ROLES = (
    "Society Admin", "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member", "Manager",
)


def upgrade():
    bind = op.get_bind()
    now = datetime.utcnow()
    row = bind.execute(sa.text("SELECT id FROM forms WHERE code = :c"), {"c": FORM_CODE}).first()
    if row:
        form_id = row[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(sa.text("""
            INSERT INTO forms (id, code, name, description, created_at, updated_at, is_active)
            VALUES (:id, :code, 'Defaulters',
                    'Members'' dues aged by how long they are outstanding, defaulters and reminders',
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
