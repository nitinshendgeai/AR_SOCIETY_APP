"""Register the Assets, Stores and Notices screens

Revision ID: 2c9d0e1f2a3b
Revises: 1b8c9d0e1f2a
Create Date: 2026-10-07

A new screen is only shown to a role once its form is registered and granted, and roles that already exist are not
granted new forms automatically. This registers "assets" and "inventory" (Admin, committee, Manager) and "notices"
(every role) and grants them to the roles that exist. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = '2c9d0e1f2a3b'
down_revision = '1b8c9d0e1f2a'
branch_labels = None
depends_on    = None

_MANAGEMENT = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer",
               "Committee Member", "Manager")
_EVERYONE = _MANAGEMENT + ("Platform Admin", "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
                           "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer",
                           "Resident", "Tenant")

FORMS = (
    ("assets", "Assets",
     "Society-owned assets (lifts, pumps, ACs, generators): warranty, service schedule and history", _MANAGEMENT),
    ("inventory", "Stores", "Consumable stock, stock in, issue to staff and return", _MANAGEMENT),
    ("notices", "Notices", "Notice board: notices for the society, acknowledgements and emergency alerts", _EVERYONE),
)


def upgrade():
    bind = op.get_bind()
    now = datetime.utcnow()
    for code, name, description, roles in FORMS:
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
        """), {"names": list(roles), "form_id": form_id}).fetchall()
        for (role_id,) in missing:
            bind.execute(sa.text("""
                INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
                VALUES (:id, :role_id, :form_id, :now, :now, true)
            """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    codes = ", ".join(f"'{c}'" for c, *_ in FORMS)
    op.execute(f"DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code IN ({codes}))")
    op.execute(f"DELETE FROM forms WHERE code IN ({codes})")
