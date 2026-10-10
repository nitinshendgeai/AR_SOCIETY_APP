"""Certificate / NOC requests and their screen.

Revision ID: c2a9102b3c4d
Revises: b1f8091a2b3c
Create Date: 2026-10-09

Registers the "certificates" screen and grants it to every role (members ask; Society Admin and committee decide, in
the API). Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'c2a9102b3c4d'
down_revision = 'b1f8091a2b3c'
branch_labels = None
depends_on    = None

UUID = postgresql.UUID(as_uuid=True)
_ROLES = ("Platform Admin", "Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer",
          "Committee Member", "Manager", "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
          "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer", "Resident", "Tenant")


def upgrade():
    bind = op.get_bind()
    if "certificate_requests" not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            "certificate_requests",
            sa.Column("id", UUID, primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("society_id", UUID, sa.ForeignKey("societies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("flat_id", UUID, sa.ForeignKey("flats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("requested_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("applicant_name", sa.String(200), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=True),
            sa.Column("party_name", sa.String(200), nullable=True),
            sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
            sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("decided_on", sa.Date(), nullable=True),
            sa.Column("decision_note", sa.Text(), nullable=True),
            sa.Column("dues_at_decision", sa.Numeric(12, 2), nullable=True),
            sa.Column("certificate_no", sa.String(40), nullable=True),
            sa.UniqueConstraint("society_id", "certificate_no", name="uq_certificate_no"),
        )
        op.create_index("ix_certificate_requests_society_id", "certificate_requests", ["society_id"])
        op.create_index("ix_certificate_requests_flat_id", "certificate_requests", ["flat_id"])
        op.create_index("ix_certificate_requests_requested_by", "certificate_requests", ["requested_by"])
        op.create_index("ix_certificate_requests_status", "certificate_requests", ["status"])

    now = datetime.utcnow()
    row = bind.execute(sa.text("SELECT id FROM forms WHERE code = 'certificates'")).first()
    if row:
        form_id = row[0]
    else:
        form_id = uuid.uuid4()
        bind.execute(sa.text("""
            INSERT INTO forms (id, code, name, description, created_at, updated_at, is_active)
            VALUES (:id, 'certificates', 'Certificates & NOC',
                    'Requests for NOCs and certificates, with approval and PDF', :now, :now, true)
        """), {"id": form_id, "now": now})
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
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'certificates')")
    op.execute("DELETE FROM forms WHERE code = 'certificates'")
    op.drop_table("certificate_requests")
