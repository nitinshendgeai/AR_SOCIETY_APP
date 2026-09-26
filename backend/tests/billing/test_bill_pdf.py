"""Maintenance bill PDF — laid out like a Mumbai housing society's
maintenance bill: boxed society header, member/flat/bill no./dates/area,
every charge head (0.00 when not charged), principal arrears and
accumulated interest, grand total in words, the numbered notes, and the
receipt for the previous bill's payment."""
import re
from datetime import date
from uuid import UUID

from app.models.resident import Resident
from decimal import Decimal

from app.modules.billing.models.billing import (
    ChargeType, InvoiceLineItem, MaintenanceBill, PaymentMode, PaymentReceipt,
)
from app.modules.billing.services.bill_pdf import _inr, amount_in_words, generate_maintenance_bill_pdf, rs_in_words
from app.modules.billing.services.billing_service import BillingService
from tests.billing.test_maintenance_billing import _charge, _cycle, _generated_cycle


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
    assert rs_in_words(3155) == "Rs. Three Thousand One Hundred Fifty Five only."


def _bill_pdf(db, bill_id):
    """The bill and its text; wrapped lines re-joined, runs of spaces collapsed."""
    svc = BillingService(db)
    bill = svc.get_bill(bill_id)
    pdf = generate_maintenance_bill_pdf(bill, svc.get_maintenance_settings(bill.society_id),
                                        compress=False, **svc._bill_print_context(bill))
    return bill, " ".join(_text(pdf).replace("|", " ").split())


def test_bill_carries_society_identity_member_charges_totals_and_notes(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf1")
    society.registration_number = "MUM/HSG/TC/9876/2015"
    society.address, society.city, society.pincode = "Plot 7, Sector 3", "Navi Mumbai", "400703"
    society.gst_number = "27AAAAA0000A1Z5"
    flat1.area_sqft = 437
    db.commit()
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={
        "bank_account_name": "MB Society pdf1 CHS Ltd", "bank_name": "Saraswat Bank",
        "bank_account_number": "1234 5678 9012", "bank_ifsc": "srcb0000123", "upi_id": "mbsociety@sbi",
        "interest_rate_pct": "21", "interest_grace_days": 5,
        "bill_notes": "Parking stickers are issued at the office.",
    }, headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert (r.json()["bank_ifsc"], r.json()["bank_account_number"]) == ("SRCB0000123", "123456789012")
    # A head this flat isn't charged still prints, at 0.00 — as on a society bill
    assert _charge(client, manager["headers"], society.id, name="Festival Fund", amount="0.00").status_code == 201
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill_id = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one().id

    bill, text = _bill_pdf(db, bill_id)
    for expected in [
        "MB SOCIETY PDF1", "Regn. No. MUM/HSG/TC/9876/2015",
        "PLOT 7, SECTOR 3, NAVI MUMBAI, MAHARASHTRA 400703.", "GSTIN: 27AAAAA0000A1Z5",
        "TAX INVOICE",                              # the water head carries 18% GST
        "Name : ASHA RAO", "FLAT NO Tower A 101",
        f"Bill No. : {bill.invoice_number}", f"Bill Date : {bill.bill_date:%d/%m/%Y}",
        f"Due Date {bill.due_date:%d/%m/%Y}", "Area Carpet: 437 Sq. Feet",
        "P a r t i c u l a r s Amount (in Rs.)",
        "Maintenance 2,500.00 Water 300.00 Festival Fund 0.00 GST @ 18% 54.00",
        "Principal Amount Dues : 0.00 Total : 2,854.00",    # 2,500 + 300 + 18% of 300
        "Accumulated Interest 0.00 Arrears / Advance 0.00",
        "Interest on Principal Arrears 0.00",
        "Rs. Two Thousand Eight Hundred Fifty Four only. Grand Total : 2,854.00",
        "1. PL. INFORM SOCIETY OFFICE WITHIN 7 DAYS IN CASE OF DISCREPANCY IF ANY.",
        "INT @21% P.A. WILL BE LEVIED ON UNPAID BILLS AFTER THE DUE DATE (GRACE PERIOD 5 DAYS).",
        "3. YOU CAN PAY BILL BY NEFT fvg. MB SOCIETY PDF1 CHS LTD. SARASWAT BANK A/C No.123456789012 "
        "IFSC :SRCB0000123. UPI ID: mbsociety@sbi.",
        "4. Parking stickers are issued at the office.",
        "5. RECEIPT ARE SUBJECT TO REALISATION OF CHEQUE.",
        "For MB SOCIETY PDF1", "HON. SECRETARY / TREASURER / CHAIRMAN",
    ]:
        assert expected in text, expected
    assert "RECEIPT for Previous Bill" not in text      # the flat's first bill


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
    assert "Name : VIK MEHTA" in text
    # Payments are acknowledged on their own receipt, never on the bill
    assert r.json()["receipt_number"] not in text and "Receipt No." not in text and "Received" not in text


def test_arrears_split_into_principal_and_accumulated_interest(client, db):
    """Arrears print as principal plus the interest billed earlier and still
    unpaid; the earlier bill's payment is not printed on this bill."""
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf4")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    first = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    # Interest billed on the first bill, and a part payment by cheque
    db.add(InvoiceLineItem(bill_id=first.id, charge_type=ChargeType.PENALTY, description="Interest on arrears",
                           unit_rate=46, amount=46, total=46))
    first.total_amount += 46
    db.add(PaymentReceipt(society_id=society.id, bill_id=first.id, flat_id=flat1.id, receipt_number="10763",
                          payment_date=date(2026, 7, 28), amount=Decimal("2000.00"),
                          payment_mode=PaymentMode.CHEQUE, cheque_number="004512", bank_name="UBI"))
    first.paid_amount = Decimal("2000.00")
    first.outstanding = first.total_amount - first.paid_amount       # 2,854 + 46 - 2,000 = 900
    db.commit()

    second_cycle = _cycle(client, manager["headers"], society.id, name="Nov 2026").json()["id"]
    r = client.post(f"/api/v1/billing/cycles/{second_cycle}/generate-bills", headers=manager["headers"])
    assert r.status_code == 200, r.text
    second = db.query(MaintenanceBill).filter_by(cycle_id=UUID(second_cycle), flat_id=flat1.id).one()
    assert second.previous_dues == Decimal("900.00")

    _, text = _bill_pdf(db, second.id)
    for expected in ["Principal Amount Dues : 854.00", "Accumulated Interest 46.00", "Arrears / Advance 900.00",
                     "Rs. Three Thousand Seven Hundred Fifty Four only. Grand Total : 3,754.00"]:
        assert expected in text, expected
    assert "10763" not in text and "Receipt No." not in text


def test_bill_payment_details_are_validated(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf3")
    for field, bad in (("bank_ifsc", "SBI123"), ("upi_id", "no-at-sign"), ("bank_account_number", "12AB")):
        r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={field: bad},
                       headers=manager["headers"])
        assert r.status_code == 422, (field, r.text)
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={"upi_id": "  "},
                   headers=manager["headers"])
    assert r.status_code == 200 and r.json()["upi_id"] is None
