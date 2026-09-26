"""Maintenance bill PDF — laid out like a housing society's maintenance
bill: society identity, member/flat/period, charges (GST column when
charged), arrears and total payable in words, payments, where to pay, and
the bye-law notes."""
import re
from datetime import date
from uuid import UUID

from app.models.resident import Resident
from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.bill_pdf import _inr, amount_in_words, generate_maintenance_bill_pdf
from app.modules.billing.services.billing_service import BillingService
from tests.billing.test_maintenance_billing import _generated_cycle


def _text(pdf: bytes) -> str:
    """The text runs of an uncompressed PDF, joined with '|'."""
    runs = re.findall(rb"\((.*?)\) Tj", pdf)
    return "|".join(r.decode("latin1").replace("\\(", "(").replace("\\)", ")") for r in runs)


def test_amounts_use_indian_grouping_and_words():
    assert _inr(1234567.8) == "12,34,567.80"
    assert _inr(999) == "999.00"
    assert amount_in_words(6815.46) == "Rupees Six Thousand Eight Hundred Fifteen and Paise Forty Six Only"
    assert amount_in_words(100000) == "Rupees One Lakh Only"
    assert amount_in_words(12345678) == \
        "Rupees One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Only"


def _bill_pdf(db, bill_id):
    svc = BillingService(db)
    bill = svc.get_bill(bill_id)
    return bill, _text(generate_maintenance_bill_pdf(bill, svc.get_maintenance_settings(bill.society_id),
                                                     compress=False))


def test_bill_carries_society_identity_member_charges_totals_and_notes(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf1")
    society.registration_number = "MUM/HSG/TC/9876/2015"
    society.address, society.city, society.pincode = "Plot 7, Sector 3", "Navi Mumbai", "400703"
    society.gst_number = "27AAAAA0000A1Z5"
    db.commit()
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={
        "bank_account_name": "MB Society pdf1 CHS Ltd", "bank_name": "Saraswat Bank",
        "bank_account_number": "1234 5678 9012", "bank_ifsc": "srcb0000123", "upi_id": "mbsociety@sbi",
        "interest_rate_pct": "12", "interest_grace_days": 5,
        "bill_notes": "Parking stickers are issued at the office.",
    }, headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert (r.json()["bank_ifsc"], r.json()["bank_account_number"]) == ("SRCB0000123", "123456789012")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill_id = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one().id

    bill, text = _bill_pdf(db, bill_id)
    for expected in [
        "MB Society pdf1", "Regn. No.: MUM/HSG/TC/9876/2015", "Plot 7, Sector 3, Navi Mumbai, Maharashtra, 400703",
        "GSTIN: 27AAAAA0000A1Z5",
        "MAINTENANCE BILL / TAX INVOICE",          # the water head carries 18% GST
        "Asha Rao", "Tower A - 101", bill.invoice_number,
        "Maintenance", "Water", "GST",
        "Rs. 2,854.00",                            # 2,500 + 300 + 18% of 300
        "Rupees Two Thousand Eight Hundred Fifty Four Only",
        "Account No.", "123456789012", "SRCB0000123", "mbsociety@sbi",
        "Simple interest at 12% per annum is charged on amounts not paid by the due date "
        "(after a grace period of 5 days)",
        "Parking stickers are issued at the office.",
        "Hon. Secretary / Treasurer",
    ]:
        assert expected in text, expected


def test_payments_and_member_fallback_on_the_bill(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf2")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat2.id).one()
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": str(flat2.id), "amount": "1000.00", "payment_date": str(date.today()),
        "payment_mode": "cash", "bill_id": str(bill.id),
    }, headers=manager["headers"])
    assert r.status_code == 201, r.text
    # A bill not linked to a resident is addressed to the flat's primary owner.
    bill.resident_id = None
    db.add(Resident(full_name="Zed Tenant", flat_id=flat2.id, resident_type="family"))
    db.commit()
    db.expire_all()

    bill, text = _bill_pdf(db, bill.id)
    assert "Vik Mehta" in text
    receipt_no = r.json()["receipt_number"]
    assert f"Payments received against this bill|Receipt No.|Date|Mode|Reference|Amount (Rs.)|{receipt_no}|" in text
    assert "Cash|" in text and "|1,000.00|" in text
    assert "Balance of this bill: |Rs. 1,854.00" in text


def test_bill_payment_details_are_validated(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf3")
    for field, bad in (("bank_ifsc", "SBI123"), ("upi_id", "no-at-sign"), ("bank_account_number", "12AB")):
        r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={field: bad},
                       headers=manager["headers"])
        assert r.status_code == 422, (field, r.text)
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={"upi_id": "  "},
                   headers=manager["headers"])
    assert r.status_code == 200 and r.json()["upi_id"] is None
