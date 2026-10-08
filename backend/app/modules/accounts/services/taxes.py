"""Pure, auditable GST/TDS calculation and vendor-invoice tax helpers."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.accounts.models.taxes import TaxConfiguration

CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class VendorTaxBreakdown:
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    gst_amount: Decimal
    gross_amount: Decimal
    tds_base_amount: Decimal
    tds_amount: Decimal
    net_payable_amount: Decimal


class TaxCalculationService:
    """Calculates tax without changing the accounting posting engine.

    Explicit invoice tax amounts are accepted for backward-compatible imports.
    When a tax configuration is supplied, the configured rate/component is used.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_config(self, society_id, code: str, tax_type: Optional[str] = None):
        q = self.db.query(TaxConfiguration).filter(
            TaxConfiguration.society_id == society_id,
            TaxConfiguration.code == code,
            TaxConfiguration.is_active == True,
        )
        if tax_type:
            q = q.filter(TaxConfiguration.tax_type == tax_type)
        return q.first()

    def calculate_vendor_invoice(
        self,
        society_id,
        *,
        amount,
        gst_amount=0,
        cgst_amount=0,
        sgst_amount=0,
        igst_amount=0,
        gst_rate=0,
        gst_component="NONE",
        tds_applicable=False,
        tds_rate=0,
        tds_base="taxable_amount",
        tds_amount=0,
        gst_config_code=None,
        tds_config_code=None,
        gross_amount=None,
    ) -> VendorTaxBreakdown:
        taxable = money(amount)

        if gst_config_code:
            cfg = self.get_config(society_id, gst_config_code, "GST")
            if not cfg:
                raise ValueError(f"GST configuration '{gst_config_code}' is not active")
            gst_rate = cfg.rate
            gst_component = cfg.component or "NONE"

        rate = money(gst_rate)
        if not (money(gst_amount) or money(cgst_amount) or money(sgst_amount) or money(igst_amount)) and rate:
            total_gst = money(taxable * rate / Decimal("100"))
            if gst_component == "CGST_SGST":
                cgst = money(total_gst / 2)
                sgst = total_gst - cgst
                igst = Decimal("0.00")
            elif gst_component == "IGST":
                cgst = sgst = Decimal("0.00")
                igst = total_gst
            else:
                raise ValueError("GST component must be CGST_SGST or IGST when GST rate is supplied")
        else:
            cgst, sgst, igst = money(cgst_amount), money(sgst_amount), money(igst_amount)
            supplied = money(gst_amount)
            if supplied and not money(cgst + sgst + igst):
                if gst_component == "IGST":
                    igst = supplied
                elif gst_component == "CGST_SGST":
                    cgst = money(supplied / 2)
                    sgst = supplied - cgst
                else:
                    raise ValueError("GST component must be CGST_SGST or IGST when GST amount is supplied")
            elif supplied and money(cgst + sgst + igst) != supplied:
                raise ValueError("GST amount must equal CGST + SGST + IGST")
            total_gst = money(cgst + sgst + igst)

        gross = money(gross_amount) if gross_amount is not None else money(taxable + total_gst)
        if gross != money(taxable + total_gst):
            raise ValueError("Invoice total must equal taxable amount plus GST")

        tds_cfg = None
        if tds_config_code:
            tds_cfg = self.get_config(society_id, tds_config_code, "TDS")
            if not tds_cfg:
                raise ValueError(f"TDS configuration '{tds_config_code}' is not active")
            tds_rate = tds_cfg.rate
            tds_base = tds_cfg.base_type or "taxable_amount"

        if tds_applicable:
            if money(tds_rate) <= 0:
                raise ValueError("TDS rate must be positive when TDS is applicable")
            base = gross if tds_base == "gross_amount" else taxable
            calculated_tds = money(base * money(tds_rate) / Decimal("100"))
            supplied_tds = money(tds_amount)
            if supplied_tds and supplied_tds != calculated_tds:
                raise ValueError("TDS amount does not match configured TDS rate/base")
            tds_base_amount, tds_value = base, calculated_tds
        else:
            tds_base_amount, tds_value = Decimal("0.00"), Decimal("0.00")

        return VendorTaxBreakdown(
            taxable_amount=taxable,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            gst_amount=total_gst,
            gross_amount=gross,
            tds_base_amount=tds_base_amount,
            tds_amount=tds_value,
            net_payable_amount=money(gross - tds_value),
        )


class TaxReportService:
    """Invoice-level GST input and TDS registers for reconciliation/audit."""

    def __init__(self, db: Session):
        self.db = db

    def gst_input_register(self, society_id, date_from=None, date_to=None):
        from app.modules.vendor.models.vendor import VendorInvoice
        q = self.db.query(VendorInvoice).filter(
            VendorInvoice.society_id == society_id,
            VendorInvoice.gst_amount > 0,
            VendorInvoice.is_active == True,
        )
        if date_from:
            q = q.filter(VendorInvoice.invoice_date >= date_from)
        if date_to:
            q = q.filter(VendorInvoice.invoice_date <= date_to)
        return q.order_by(VendorInvoice.invoice_date, VendorInvoice.invoice_number).all()

    def tds_register(self, society_id, date_from=None, date_to=None):
        from app.modules.vendor.models.vendor import VendorInvoice
        q = self.db.query(VendorInvoice).filter(
            VendorInvoice.society_id == society_id,
            VendorInvoice.tds_amount > 0,
            VendorInvoice.is_active == True,
        )
        if date_from:
            q = q.filter(VendorInvoice.invoice_date >= date_from)
        if date_to:
            q = q.filter(VendorInvoice.invoice_date <= date_to)
        return q.order_by(VendorInvoice.invoice_date, VendorInvoice.invoice_number).all()
