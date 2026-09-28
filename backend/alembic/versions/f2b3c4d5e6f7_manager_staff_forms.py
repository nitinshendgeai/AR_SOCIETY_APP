"""Manager gets the Staff and Checklist Templates screens

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-27

The Manager runs the society's staff (master, attendance, duties, leaves,
roster, checklist templates), so the Staff and Checklist Templates screens
join their menu (FORM_ROLE_GRANTS in app/core/rbac_seed.py covers new roles;
this grants them to the Manager role that already exists). Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision      = 'f2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on    = None

def upgrade():
    bind = op.get_bind()
    missing = bind.execute(sa.text("""
        SELECT r.id, f.id
        FROM roles r JOIN forms f ON f.code IN ('staff', 'checklist_templates')
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
          AND form_id IN (SELECT id FROM forms WHERE code IN ('staff', 'checklist_templates'))
    """)
