from decimal import Decimal
import pytest

from app.modules.accounts.services.taxes import TaxCalculationService


def test_vendor_tax_breakdown_cgst_sgst_and_tds():
    tax = TaxCalculationService(None).calculate_vendor_invoice(
        "society",
        amount="10000.00",
        gst_rate="18",
        gst_component="CGST_SGST",
        tds_applicable=True,
        tds_rate="2",
        tds_base="taxable_amount",
        tds_section="194C",
        gross_amount="11800.00",
    )
    assert tax.cgst_amount == Decimal("900.00")
    assert tax.sgst_amount == Decimal("900.00")
    assert tax.gst_amount == Decimal("1800.00")
    assert tax.tds_amount == Decimal("200.00")
    assert tax.net_payable_amount == Decimal("11600.00")


def test_vendor_tax_breakdown_igst():
    tax = TaxCalculationService(None).calculate_vendor_invoice(
        "society",
        amount="5000.00",
        gst_amount="900.00",
        gst_component="IGST",
        gross_amount="5900.00",
    )
    assert tax.cgst_amount == Decimal("0.00")
    assert tax.sgst_amount == Decimal("0.00")
    assert tax.igst_amount == Decimal("900.00")


def test_vendor_tax_rejects_mismatched_total():
    with pytest.raises(ValueError, match="Invoice total"):
        TaxCalculationService(None).calculate_vendor_invoice(
            "society",
            amount="10000.00",
            gst_rate="18",
            gst_component="CGST_SGST",
            gross_amount="10000.00",
        )


def test_vendor_tax_rejects_tds_without_rate():
    with pytest.raises(ValueError, match="TDS rate"):
        TaxCalculationService(None).calculate_vendor_invoice(
            "society",
            amount="10000.00",
            tds_applicable=True,
            gross_amount="10000.00",
        )
