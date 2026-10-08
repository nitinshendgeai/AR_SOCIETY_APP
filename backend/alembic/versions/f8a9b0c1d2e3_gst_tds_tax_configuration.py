"""Add configurable GST/TDS master and vendor invoice tax breakdown."""
from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "e6f7a8b9c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "accounting_tax_configurations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("society_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("tax_type", sa.String(10), nullable=False),
        sa.Column("rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("component", sa.String(20), nullable=True),
        sa.Column("section_code", sa.String(30), nullable=True),
        sa.Column("base_type", sa.String(30), nullable=True),
        sa.Column("threshold_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("ledger_system_key", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["society_id"], ["societies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("society_id", "code", name="uq_tax_config_society_code"),
    )
    op.create_index("ix_accounting_tax_configurations_society_id", "accounting_tax_configurations", ["society_id"])
    op.create_index("ix_accounting_tax_configurations_tax_type", "accounting_tax_configurations", ["tax_type"])
    op.create_index("ix_accounting_tax_configurations_is_active", "accounting_tax_configurations", ["is_active"])

    for key, code, name in (
        ("gst_input_cgst", "2307", "Input GST - CGST"),
        ("gst_input_sgst", "2308", "Input GST - SGST"),
        ("gst_input_igst", "2309", "Input GST - IGST"),
    ):
        op.execute(sa.text(
            "INSERT INTO accounts (id, society_id, group_id, code, name, system_key, is_system, opening_type, sort_order) "
            "SELECT gen_random_uuid(), g.society_id, g.id, :code, :name, :key, true, 'dr', 999 "
            "FROM account_groups g "
            "WHERE g.system_key='current_assets' "
            "AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.society_id=g.society_id AND a.system_key=:key)"
        ).bindparams(key=key, code=code, name=name))

    op.add_column("vendor_invoices", sa.Column("gst_rate", sa.Numeric(7, 4), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("gst_component", sa.String(20), nullable=False, server_default="NONE"))
    op.add_column("vendor_invoices", sa.Column("cgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("sgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("igst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("gst_itc_eligible", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("vendor_invoices", sa.Column("tds_applicable", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("vendor_invoices", sa.Column("tds_section", sa.String(30), nullable=True))
    op.add_column("vendor_invoices", sa.Column("tds_rate", sa.Numeric(7, 4), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("tds_base_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("tds_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("vendor_invoices", sa.Column("net_payable_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("vendor_invoices", sa.Column("gst_config_code", sa.String(40), nullable=True))
    op.add_column("vendor_invoices", sa.Column("tds_config_code", sa.String(40), nullable=True))

    op.execute(sa.text(
        "UPDATE vendor_invoices SET gst_component = 'NONE', "
        "net_payable_amount = total_amount WHERE net_payable_amount IS NULL"
    ))


def downgrade():
    for c in ("tds_config_code", "gst_config_code", "net_payable_amount", "tds_amount", "tds_base_amount",
              "tds_rate", "tds_section", "tds_applicable", "igst_amount", "sgst_amount", "cgst_amount",
              "gst_component", "gst_rate", "gst_itc_eligible"):
        op.drop_column("vendor_invoices", c)
    op.drop_index("ix_accounting_tax_configurations_is_active", table_name="accounting_tax_configurations")
    op.drop_index("ix_accounting_tax_configurations_tax_type", table_name="accounting_tax_configurations")
    op.drop_index("ix_accounting_tax_configurations_society_id", table_name="accounting_tax_configurations")
    op.drop_table("accounting_tax_configurations")
