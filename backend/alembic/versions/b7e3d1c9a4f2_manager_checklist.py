"""Manager's daily checklist

Revision ID: b7e3d1c9a4f2
Revises: e4c1324d5e6f
Create Date: 2026-10-11

The checklist items a society's manager works through (the built-in ones are added the first time the checklist is
opened), what has been ticked against them, and the end-of-day sign-off. Also registers the "manager_checklist"
screen and grants it to the admin, committee and manager roles. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'b7e3d1c9a4f2'
down_revision = 'e4c1324d5e6f'
branch_labels = None
depends_on    = None

CODE, NAME = "manager_checklist", "Manager's Checklist"
DESCRIPTION = "The manager's daily work: routine by assets and staff, what needs attention, and statutory dates"
_ROLES = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member",
          "Manager")


def _base():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    bind = op.get_bind()
    have = set(sa.inspect(bind).get_table_names())
    soc = lambda: sa.Column("society_id", postgresql.UUID(as_uuid=True),  # noqa: E731
                            sa.ForeignKey("societies.id", ondelete="CASCADE"), nullable=False)
    usr = lambda name: sa.Column(name, postgresql.UUID(as_uuid=True),  # noqa: E731
                                 sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    if "manager_checklist_items" not in have:
        op.create_table(
            "manager_checklist_items", *_base(), soc(),
            sa.Column("code", sa.String(60), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("category", sa.String(20), nullable=False, server_default="housekeeping"),
            sa.Column("frequency", sa.String(10), nullable=False, server_default="daily"),
            sa.Column("due_weekday", sa.Integer(), nullable=True),
            sa.Column("due_day", sa.Integer(), nullable=True),
            sa.Column("due_months", sa.String(40), nullable=True),
            sa.Column("lead_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("asset_category", sa.String(30), nullable=True),
            sa.Column("staff_department", sa.String(30), nullable=True),
            sa.Column("statutory", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("legal_basis", sa.Text(), nullable=True),
            sa.Column("jurisdiction", sa.String(20), nullable=True),
            sa.Column("link_key", sa.String(30), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
            usr("created_by"),
            sa.UniqueConstraint("society_id", "code", name="uq_checklist_society_code"),
        )
        op.create_index("ix_manager_checklist_items_society_id", "manager_checklist_items", ["society_id"])

    if "manager_checklist_logs" not in have:
        op.create_table(
            "manager_checklist_logs", *_base(), soc(),
            sa.Column("item_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("manager_checklist_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("for_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(10), nullable=False, server_default="done"),
            sa.Column("done_on", sa.Date(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("reference", sa.String(120), nullable=True),
            sa.Column("valid_until", sa.Date(), nullable=True),
            usr("done_by"),
            sa.UniqueConstraint("item_id", "for_date", name="uq_checklist_log_item_date"),
        )
        op.create_index("ix_manager_checklist_logs_society_id", "manager_checklist_logs", ["society_id"])
        op.create_index("ix_manager_checklist_logs_item_id", "manager_checklist_logs", ["item_id"])
        op.create_index("ix_manager_checklist_logs_for_date", "manager_checklist_logs", ["for_date"])

    if "manager_checklist_signoffs" not in have:
        op.create_table(
            "manager_checklist_signoffs", *_base(), soc(),
            sa.Column("for_date", sa.Date(), nullable=False),
            usr("signed_by"),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("routine_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("routine_done", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("live_open", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("society_id", "for_date", name="uq_checklist_signoff_day"),
        )
        op.create_index("ix_manager_checklist_signoffs_society_id", "manager_checklist_signoffs", ["society_id"])
        op.create_index("ix_manager_checklist_signoffs_for_date", "manager_checklist_signoffs", ["for_date"])

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
    """), {"names": list(_ROLES), "form_id": form_id}).fetchall()
    for (role_id,) in missing:
        bind.execute(sa.text("""
            INSERT INTO role_forms (id, role_id, form_id, created_at, updated_at, is_active)
            VALUES (:id, :role_id, :form_id, :now, :now, true)
        """), {"id": uuid.uuid4(), "role_id": role_id, "form_id": form_id, "now": now})


def downgrade():
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'manager_checklist')")
    op.execute("DELETE FROM forms WHERE code = 'manager_checklist'")
    for t in ("manager_checklist_signoffs", "manager_checklist_logs", "manager_checklist_items"):
        op.drop_table(t)
