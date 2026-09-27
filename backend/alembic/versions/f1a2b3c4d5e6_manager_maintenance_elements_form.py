"""Manager gets the Maintenance Elements screen

Revision ID: f1a2b3c4d5e6
Revises: f0a1b2c3d4e5
Create Date: 2026-09-27

The Manager runs maintenance billing, so besides Maintenance Billing they
now see Maintenance Elements too (FORM_ROLE_GRANTS in app/core/rbac_seed.py
covers new roles; this grants it to the Manager role that already exists).
Idempotent: nothing happens if the form or role is missing or the grant is
already there.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = 'f1a2b3c4d5e6'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on    = None


def upgrade():
    bind = op.get_bind()
    missing = bind.execute(sa.text("""
        SELECT r.id, f.id
        FROM roles r JOIN forms f ON f.code = 'maintenance_elements'
        WHERE r.name = 'Manager'
          AND NOT EXISTS (SELECT 1 FROM role_forms x WHERE x.role_id = r.id AND x.form_id = f.id)
    """)).fetchall()
    now = datetime.utcnow()
    for role_id, form_id in missing:
        bind.execute(sa.text("""
            INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
            VALUES (:id, :role_id, :form_id, :now, :now, true)
        """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    op.execute("""
        DELETE FROM role_forms
        WHERE role_id IN (SELECT id FROM roles WHERE name = 'Manager')
          AND form_id IN (SELECT id FROM forms WHERE code = 'maintenance_elements')
    """)
