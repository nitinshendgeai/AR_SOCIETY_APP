"""Gate extras: parcels at the gate, domestic help register with passes and gate entries.

Revision ID: d3b0213c4d5e
Revises: c2a9102b3c4d
Create Date: 2026-10-09

Registers the "parcels" and "domestic_help" screens and grants them to every role. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'd3b0213c4d5e'
down_revision = 'c2a9102b3c4d'
branch_labels = None
depends_on    = None

UUID = postgresql.UUID(as_uuid=True)
FORMS = (
    ("parcels", "Parcels", "Parcels and deliveries left at the gate"),
    ("domestic_help", "Domestic help", "Register of maids, cooks and drivers, with passes and gate entries"),
)
_ROLES = ("Platform Admin", "Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer",
          "Committee Member", "Manager", "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
          "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer", "Resident", "Tenant")


def _base():
    return [
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def _fk(col, target, nullable=False):
    return sa.Column(col, UUID, sa.ForeignKey(target, ondelete="CASCADE" if not nullable else "SET NULL"),
                     nullable=nullable)


def upgrade():
    bind = op.get_bind()
    have = set(sa.inspect(bind).get_table_names())

    if "gate_parcels" not in have:
        op.create_table(
            "gate_parcels", *_base(), _fk("society_id", "societies.id"), _fk("flat_id", "flats.id"),
            sa.Column("courier", sa.String(120), nullable=True),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("recipient_name", sa.String(120), nullable=True),
            sa.Column("status", sa.String(12), nullable=False, server_default="at_gate"),
            sa.Column("received_at", sa.DateTime(), nullable=False),
            _fk("logged_by", "users.id", nullable=True),
            sa.Column("collected_at", sa.DateTime(), nullable=True),
            sa.Column("collected_by_name", sa.String(120), nullable=True),
            _fk("closed_by", "users.id", nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
        )
        op.create_index("ix_gate_parcels_society_id", "gate_parcels", ["society_id"])
        op.create_index("ix_gate_parcels_flat_id", "gate_parcels", ["flat_id"])
        op.create_index("ix_gate_parcels_status", "gate_parcels", ["status"])
    if "domestic_help" not in have:
        op.create_table(
            "domestic_help", *_base(), _fk("society_id", "societies.id"),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("mobile", sa.String(20), nullable=False),
            sa.Column("kind", sa.String(12), nullable=False, server_default="maid"),
            sa.Column("id_proof", sa.String(120), nullable=True),
            sa.Column("police_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("pass_no", sa.String(20), nullable=True),
            sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
            sa.Column("valid_until", sa.Date(), nullable=True),
            _fk("registered_by", "users.id", nullable=True),
            _fk("approved_by", "users.id", nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.UniqueConstraint("society_id", "pass_no", name="uq_domestic_help_pass"),
        )
        op.create_index("ix_domestic_help_society_id", "domestic_help", ["society_id"])
        op.create_index("ix_domestic_help_mobile", "domestic_help", ["mobile"])
        op.create_index("ix_domestic_help_status", "domestic_help", ["status"])
    if "domestic_help_flats" not in have:
        op.create_table(
            "domestic_help_flats", *_base(), _fk("help_id", "domestic_help.id"), _fk("flat_id", "flats.id"),
            sa.UniqueConstraint("help_id", "flat_id", name="uq_domestic_help_flat"),
        )
        op.create_index("ix_domestic_help_flats_help_id", "domestic_help_flats", ["help_id"])
        op.create_index("ix_domestic_help_flats_flat_id", "domestic_help_flats", ["flat_id"])
    if "domestic_help_entries" not in have:
        op.create_table(
            "domestic_help_entries", *_base(), _fk("help_id", "domestic_help.id"), _fk("society_id", "societies.id"),
            sa.Column("in_at", sa.DateTime(), nullable=False),
            sa.Column("out_at", sa.DateTime(), nullable=True),
            _fk("logged_by", "users.id", nullable=True),
        )
        op.create_index("ix_domestic_help_entries_help_id", "domestic_help_entries", ["help_id"])
        op.create_index("ix_domestic_help_entries_society_id", "domestic_help_entries", ["society_id"])
        op.create_index("ix_domestic_help_entries_in_at", "domestic_help_entries", ["in_at"])

    now = datetime.utcnow()
    for code, name, description in FORMS:
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
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code IN "
               "('parcels','domestic_help'))")
    op.execute("DELETE FROM forms WHERE code IN ('parcels','domestic_help')")
    for t in ("domestic_help_entries", "domestic_help_flats", "domestic_help", "gate_parcels"):
        op.drop_table(t)
