"""Shops master

Revision ID: 8c5d6e7f8091
Revises: 7b4c5d6e7f80
Create Date: 2026-10-09

The shops of a society, kept apart from its flats: owner, occupancy, possession date and electricity meter. Also
registers the "shops" screen and grants it to the admin and committee roles. Idempotent.
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = '8c5d6e7f8091'
down_revision = '7b4c5d6e7f80'
branch_labels = None
depends_on    = None

CODE, NAME = "shops", "Shops"
DESCRIPTION = "Shop master: owners, possession dates and electricity meters; bulk import"
_ROLES = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member")


def upgrade():
    bind = op.get_bind()
    if "shops" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "shops",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("shop_number", sa.String(30), nullable=False),
            sa.Column("floor", sa.Integer(), nullable=True),
            sa.Column("location", sa.String(120), nullable=True),
            sa.Column("area_sqft", sa.Float(), nullable=True),
            sa.Column("business_name", sa.String(150), nullable=True),
            sa.Column("owner_name", sa.String(255), nullable=False),
            sa.Column("owner_phone", sa.String(20), nullable=True),
            sa.Column("owner_email", sa.String(255), nullable=True),
            sa.Column("occupancy", sa.String(20), nullable=False, server_default="vacant"),
            sa.Column("tenant_name", sa.String(255), nullable=True),
            sa.Column("tenant_phone", sa.String(20), nullable=True),
            sa.Column("possession_date", sa.Date(), nullable=True),
            sa.Column("electric_meter_no", sa.String(40), nullable=True),
            sa.Column("electric_consumer_no", sa.String(40), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"),
                      nullable=True),
        )
        op.create_index("ix_shops_society_id", "shops", ["society_id"])
        op.create_index("uq_shop_society_number", "shops", ["society_id", "shop_number"], unique=True,
                        postgresql_where=sa.text("is_active = true"))

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
    op.execute("DELETE FROM role_forms WHERE form_id IN (SELECT id FROM forms WHERE code = 'shops')")
    op.execute("DELETE FROM forms WHERE code = 'shops'")
    op.drop_index("uq_shop_society_number", table_name="shops")
    op.drop_index("ix_shops_society_id", table_name="shops")
    op.drop_table("shops")
