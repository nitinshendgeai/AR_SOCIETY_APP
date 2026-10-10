"""Automatic tasks: per-society switches, the run log, and the Automatic tasks screen.

Revision ID: a0e7f8091a2b
Revises: 9d6e7f8091a2
Create Date: 2026-10-09

`society_automation` holds which tasks a society has switched on; `scheduled_job_runs` records each run
(its unique key makes a task run once per day or week however many workers there are). Also registers the
"automation" screen and grants it to the admin and committee roles. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'a0e7f8091a2b'
down_revision = '9d6e7f8091a2'
branch_labels = None
depends_on    = None

CODE, NAME = "automation", "Automatic tasks"
DESCRIPTION = "Switch reminders and alerts on or off; see what ran and run one now"
_ROLES = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member")


def _base_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "society_automation" not in tables:
        op.create_table(
            "society_automation", *_base_columns(),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("dues_reminders", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("reminder_every_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("reminder_min_months", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("agreement_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("asset_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("billing_nudge", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("visitor_expiry", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("society_id", name="uq_society_automation_society"),
        )
        op.create_index("ix_society_automation_society_id", "society_automation", ["society_id"])
    if "scheduled_job_runs" not in tables:
        op.create_table(
            "scheduled_job_runs", *_base_columns(),
            sa.Column("job", sa.String(50), nullable=False),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("period_key", sa.String(40), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="running"),
            sa.Column("manual", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("job", "society_id", "period_key", name="uq_scheduled_job_run"),
        )
        op.create_index("ix_scheduled_job_runs_job", "scheduled_job_runs", ["job"])
        op.create_index("ix_scheduled_job_runs_society_id", "scheduled_job_runs", ["society_id"])

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
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'automation')")
    op.execute("DELETE FROM forms WHERE code = 'automation'")
    op.drop_table("scheduled_job_runs")
    op.drop_table("society_automation")
