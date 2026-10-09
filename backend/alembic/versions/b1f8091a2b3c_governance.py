"""Governance: meetings and minutes, polls, society documents, and their three screens.

Revision ID: b1f8091a2b3c
Revises: a0e7f8091a2b
Create Date: 2026-10-09

Registers the "meetings", "polls" and "documents" screens and grants them to every role (read access; the
actions themselves are limited to Society Admin and committee in the API). Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = 'b1f8091a2b3c'
down_revision = 'a0e7f8091a2b'
branch_labels = None
depends_on    = None

UUID = postgresql.UUID(as_uuid=True)
FORMS = (
    ("meetings", "Meetings", "Meetings, agendas, minutes and resolutions"),
    ("polls", "Polls", "Polls and voting, one vote per flat"),
    ("documents", "Documents", "The society's documents: bye-laws, minutes, audit reports"),
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

    if "meetings" not in have:
        op.create_table(
            "meetings", *_base(), _fk("society_id", "societies.id"),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("meeting_type", sa.String(20), nullable=False, server_default="committee"),
            sa.Column("meeting_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=True),
            sa.Column("venue", sa.String(200), nullable=True),
            sa.Column("agenda", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
            sa.Column("minutes", sa.Text(), nullable=True),
            sa.Column("minutes_published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("minutes_published_on", sa.Date(), nullable=True),
            _fk("created_by", "users.id", nullable=True),
        )
        op.create_index("ix_meetings_society_id", "meetings", ["society_id"])
        op.create_index("ix_meetings_meeting_date", "meetings", ["meeting_date"])
        op.create_index("ix_meetings_status", "meetings", ["status"])
    if "meeting_attendees" not in have:
        op.create_table(
            "meeting_attendees", *_base(), _fk("meeting_id", "meetings.id"),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("flat_label", sa.String(60), nullable=True),
            sa.Column("designation", sa.String(60), nullable=True),
            sa.Column("present", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index("ix_meeting_attendees_meeting_id", "meeting_attendees", ["meeting_id"])
    if "meeting_resolutions" not in have:
        op.create_table(
            "meeting_resolutions", *_base(), _fk("meeting_id", "meetings.id"),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("proposed_by", sa.String(120), nullable=True),
            sa.Column("seconded_by", sa.String(120), nullable=True),
            sa.Column("outcome", sa.String(20), nullable=False, server_default="carried"),
        )
        op.create_index("ix_meeting_resolutions_meeting_id", "meeting_resolutions", ["meeting_id"])
    if "polls" not in have:
        op.create_table(
            "polls", *_base(), _fk("society_id", "societies.id"),
            sa.Column("question", sa.String(300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("closes_on", sa.Date(), nullable=False),
            sa.Column("closed_early", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("results_after", sa.String(10), nullable=False, server_default="vote"),
            _fk("created_by", "users.id", nullable=True),
        )
        op.create_index("ix_polls_society_id", "polls", ["society_id"])
    if "poll_options" not in have:
        op.create_table(
            "poll_options", *_base(), _fk("poll_id", "polls.id"),
            sa.Column("label", sa.String(200), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_poll_options_poll_id", "poll_options", ["poll_id"])
    if "poll_votes" not in have:
        op.create_table(
            "poll_votes", *_base(), _fk("poll_id", "polls.id"), _fk("option_id", "poll_options.id"),
            _fk("flat_id", "flats.id"), _fk("user_id", "users.id", nullable=True),
            sa.Column("voted_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("poll_id", "flat_id", name="uq_poll_vote_flat"),
        )
        op.create_index("ix_poll_votes_poll_id", "poll_votes", ["poll_id"])
    if "society_documents" not in have:
        op.create_table(
            "society_documents", *_base(), _fk("society_id", "societies.id"),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("category", sa.String(20), nullable=False, server_default="other"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(12), nullable=False, server_default="everyone"),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            _fk("uploaded_by", "users.id", nullable=True),
        )
        op.create_index("ix_society_documents_society_id", "society_documents", ["society_id"])
        op.create_index("ix_society_documents_category", "society_documents", ["category"])

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
               "('meetings','polls','documents'))")
    op.execute("DELETE FROM forms WHERE code IN ('meetings','polls','documents')")
    for t in ("poll_votes", "poll_options", "polls", "meeting_resolutions", "meeting_attendees", "meetings",
              "society_documents"):
        op.drop_table(t)
