"""Register the Amenities screen

Revision ID: 3d0e1f2a3b4c
Revises: 2c9d0e1f2a3b
Create Date: 2026-10-07

Registers the "amenities" form and grants it to every role that exists (any member may book; the committee and
manager also run the bookings and set the amenities up, which the API decides). Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = '3d0e1f2a3b4c'
down_revision = '2c9d0e1f2a3b'
branch_labels = None
depends_on    = None

_EVERYONE = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member",
             "Manager", "Platform Admin", "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
             "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer", "Resident", "Tenant")
CODE, NAME = "amenities", "Amenities"
DESCRIPTION = "Clubhouse, gym, pool and hall: book a time, rules, prices, closed dates and approvals"


def upgrade():
    bind = op.get_bind()
    now = datetime.utcnow()
    row = bind.execute(sa.text("SELECT id FROM forms WHERE code = :c"), {"c": CODE}).first()
    if row:
        form_id = row[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(sa.text("""
            INSERT INTO forms (id, code, name, description, created_at, updated_at, is_active)
            VALUES (:id, :code, :name, :description, :now, :now, true)
        """), {"id": form_id, "code": CODE, "name": NAME, "description": DESCRIPTION, "now": now})
    missing = bind.execute(sa.text("""
        SELECT r.id FROM roles r
        WHERE r.name = ANY(:names)
          AND NOT EXISTS (SELECT 1 FROM role_forms x WHERE x.role_id = r.id AND x.form_id = :form_id)
    """), {"names": list(_EVERYONE), "form_id": form_id}).fetchall()
    for (role_id,) in missing:
        bind.execute(sa.text("""
            INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
            VALUES (:id, :role_id, :form_id, :now, :now, true)
        """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'amenities')")
    op.execute("DELETE FROM forms WHERE code = 'amenities'")
