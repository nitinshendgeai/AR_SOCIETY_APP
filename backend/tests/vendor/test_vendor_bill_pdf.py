"""The vendor bill prints: the letterhead, the vendor, the bill's number and dates, the amounts with GST and TDS,
the net payable in words, the payments made, and signature lines. Managers print it, scoped to their society."""
import re
from datetime import date
from uuid import UUID

from app.modules.vendor.models.vendor import VendorInvoice
from app.modules.vendor.services.vendor_bill_pdf import render_vendor_bill_pdf
from tests.conftest import make_society, make_user, place_in
from tests.vendor.test_vendor_payments import _create_invoice, _create_vendor, _rig


def _text(pdf: bytes) -> str:
    runs = re.findall(rb"\((.*?)\) Tj", pdf)
    return " ".join(" ".join(r.decode("latin1").replace("\\(", "(").replace("\\)", ")") for r in runs).split())


def test_vendor_bill_pdf_shows_the_bill_payments_and_signature_lines(client, db):
    society, manager, admin, resident = _rig(db)
    society.registration_number = "MUM/HSG/TC/1/2020"
    db.commit()
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id, total_amount="10000.00",
                             invoice_number="CP/26-27/118", description="Housekeeping for October").json()["id"]
    r = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "4000.00", "paid_date": str(date.today()), "payment_mode": "neft", "payment_ref": "UTR998877",
    }, headers=manager["headers"])
    assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/vendors/invoices/{inv_id}/pdf", headers=manager["headers"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    assert "VendorBill-CP_26-27_118.pdf" in r.headers["content-disposition"]

    inv = db.query(VendorInvoice).filter_by(id=UUID(inv_id)).one()
    text = _text(render_vendor_bill_pdf(inv, society, compress=False))
    for expected in [
        "Regn. No. MUM/HSG/TC/1/2020", "VENDOR BILL", "CleanPro", "Bill No. CP/26-27/118",
        f"Bill Date {inv.invoice_date:%d-%b-%Y}", "Particulars: Housekeeping for October",
        "Total bill amount 10,000.00", "Net payable to the vendor 10,000.00",
        "Net payable in words: Rupees Ten Thousand Only", "Paid so far 4,000.00", "Balance to be paid 6,000.00",
        "Payments made", f"{date.today():%d-%b-%Y}", "Neft", "UTR998877",
        "Prepared by", "Checked by", "Hon. Treasurer", "Chairman",
    ]:
        assert expected in text, expected
    assert "CANCELLED" not in text


def test_vendor_bill_pdf_marks_a_cancelled_bill_and_is_limited_to_the_society(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id).json()["id"]
    inv = db.query(VendorInvoice).filter_by(id=UUID(inv_id)).one()
    inv.is_active = False
    db.commit()
    assert "CANCELLED" in _text(render_vendor_bill_pdf(inv, society, compress=False))

    assert client.get(f"/api/v1/vendors/invoices/{inv_id}/pdf", headers=resident["headers"]).status_code == 403
    other = make_society(db, "Other Society")
    stranger = place_in(db, make_user(db, "manager@other-vb.com", role="Manager"), other)
    assert client.get(f"/api/v1/vendors/invoices/{inv_id}/pdf", headers=stranger["headers"]).status_code in (403, 404)


def test_vendor_bill_pdf_nets_the_tds_and_splits_the_gst(client, db):
    from decimal import Decimal
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id, total_amount="11800.00").json()["id"]
    inv = db.query(VendorInvoice).filter_by(id=UUID(inv_id)).one()
    inv.amount, inv.gst_amount, inv.cgst_amount, inv.sgst_amount = (Decimal("10000"), Decimal("1800"),
                                                                    Decimal("900"), Decimal("900"))
    inv.tds_amount, inv.tds_section, inv.tds_rate = Decimal("200"), "194C", Decimal("2")
    inv.vendor.gst_number, inv.vendor.bank_name, inv.vendor.bank_account, inv.vendor.bank_ifsc = (
        "27AAAAA0000A1Z5", "Axis Bank", "9170100", "UTIB0000123")
    db.commit()
    text = _text(render_vendor_bill_pdf(inv, society, compress=False))
    for expected in ["CGST 900.00", "SGST 900.00", "Total bill amount 11,800.00", "Less: TDS u/s 194C @ 2% -200.00",
                     "Net payable to the vendor 11,600.00", "Balance to be paid 11,600.00",
                     "Rupees Eleven Thousand Six Hundred Only", "GSTIN 27AAAAA0000A1Z5",
                     "Bank Axis Bank, A/c 9170100, IFSC UTIB0000123"]:
        assert expected in text, expected
