"""Register the Platform Console screen

Revision ID: 5f2a3b4c5d6e
Revises: 4e1f2a3b4c5d
Create Date: 2026-10-09

Registers the "platform_admin" form and grants it to the Platform Admin role only. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = '5f2a3b4c5d6e'
down_revision = '4e1f2a3b4c5d'
branch_labels = None
depends_on    = None

CODE, NAME = "platform_admin", "Platform Console"
DESCRIPTION = "Every society on the platform: trials, plans, suspension, limits and the record of what was done"


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
        WHERE r.name = 'Platform Admin'
          AND NOT EXISTS (SELECT 1 FROM role_forms x WHERE x.role_id = r.id AND x.form_id = :form_id)
    """), {"form_id": form_id}).fetchall()
    for (role_id,) in missing:
        bind.execute(sa.text("""
            INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
            VALUES (:id, :role_id, :form_id, :now, :now, true)
        """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'platform_admin')")
    op.execute("DELETE FROM forms WHERE code = 'platform_admin'")
