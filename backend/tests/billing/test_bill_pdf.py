"""Maintenance bill PDF — laid out like a Mumbai housing society's
maintenance bill: letterhead band, member and bill details, the fixed bill
heads (monthly expenses together as "Maintenance Charges", 0.00 for heads
not charged), current bill / arrears / interest / total payable, the notes,
and the receipts towards the flat's previous bill."""
import re
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from app.models.resident import Resident

from app.modules.billing.models.billing import (
    ChargeType, InvoiceLineItem, MaintenanceBill, PaymentMode, PaymentReceipt,
)
from app.modules.billing.services.bill_pdf import (
    _bill_month, _inr, amount_in_words, bill_head, generate_maintenance_bill_pdf, rs_in_words,
)
from app.modules.billing.services.billing_service import BillingService
from tests.billing.test_maintenance_billing import _charge, _cycle, _generated_cycle, _rig


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


def test_monthly_expenses_share_one_head_and_levies_keep_their_own():
    def head(desc, charge_type=ChargeType.OTHER, code=None):
        return bill_head(SimpleNamespace(description=desc, charge_type=charge_type), code)

    for desc, ctype, code in [("Service Charges", ChargeType.MAINTENANCE, "service_charges"),
                              ("Water Charges", ChargeType.WATER, "water_charges"),
                              ("Lift Maintenance", ChargeType.MAINTENANCE, "lift_maintenance"),
                              ("Building Insurance", ChargeType.OTHER, "insurance"),
                              ("Clubhouse", ChargeType.AMENITIES, None)]:
        assert head(desc, ctype, code) == "Maintenance Charges", desc
    assert head("Property Tax", ChargeType.OTHER, "property_tax") == "Property Tax"
    assert head("Municipal Tax") == "Property Tax"
    assert head("Sinking Fund", ChargeType.SINKING_FUND) == "Sinking Fund"
    assert head("Repairs & Maintenance Fund", ChargeType.REPAIR_FUND) == "Repair & Maintenance Fund"
    assert head("Non-occupancy charges (10% of service charges)", ChargeType.MAINTENANCE) == "Non Occupancy Charges"
    assert head("Parking Charges", ChargeType.PARKING) == "Parking Charges"
    assert head("Cheque Bounce Charges") == "Cheque Bounce Charges"
    assert head("In & Out Charges") == "In & Out Charges"
    assert head("Festival Fund") == "Other Charges"
    assert head("Legal Charges", ChargeType.OTHER, "education_fund") == "Maintenance Charges"


def test_bill_layout_heads_totals_and_notes(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "pdf1")
    society.registration_number = "MUM/HSG/TC/9876/2015"
    society.address, society.city, society.pincode = "Plot 7, Sector 3", "Navi Mumbai", "400703"
    society.gst_number = "27AAAAA0000A1Z5"
    flat1.area_sqft = 437
    db.commit()
    h = manager["headers"]
    _charge(client, h, society.id, amount="2500.00")
    _charge(client, h, society.id, name="Water", amount="300.00", tax="18", charge_type="water")
    _charge(client, h, society.id, name="Sinking Fund", amount="100.00", charge_type="sinking_fund")
    _charge(client, h, society.id, name="Festival Fund", amount="50.00", charge_type="other")
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={
        "bank_account_name": "MB Society pdf1 CHS Ltd", "bank_name": "Saraswat Bank",
        "bank_account_number": "1234 5678 9012", "bank_ifsc": "srcb0000123", "upi_id": "mbsociety@sbi",
        "interest_rate_pct": "21", "interest_grace_days": 5,
        "bill_notes": "Parking stickers are issued at the office.",
    }, headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["bank_ifsc"], r.json()["bank_account_number"]) == ("SRCB0000123", "123456789012")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h)
    bill_id = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one().id

    bill, text = _bill_pdf(db, bill_id)
    cycle = bill.cycle
    for expected in [
        "MB SOCIETY PDF1",
        "Regn. No. MUM/HSG/TC/9876/2015 PLOT 7, SECTOR 3, NAVI MUMBAI, MAHARASHTRA 400703",  # "|" joins them
        "GSTIN: 27AAAAA0000A1Z5",
        "Maintenance Bill / Tax Invoice",           # the water head carries 18% GST
        "Name : Asha Rao", "Flat No. : Tower A 101", "Area sq ft : 437",
        f"Bill No. : {bill.invoice_number}", f"Bill Date : {bill.bill_date:%d-%b-%Y}",
        f"Due Date : {bill.due_date:%d-%b-%Y}",
        f"Bill Period : {cycle.cycle_start:%d-%b-%Y} to {cycle.cycle_end:%d-%b-%Y}",
        "No Head Amount (Rs.)",
        # Maintenance + Water (monthly expenses) together; levies on their own heads
        "1 Maintenance Charges 2,800.00 2 Sinking Fund 100.00 3 Repair & Maintenance Fund 0.00 "
        "4 Property Tax 0.00 5 Non Occupancy Charges 0.00 6 Parking Charges 0.00 "
        "7 Cheque Bounce Charges 0.00 8 In & Out Charges 0.00 9 Other Charges 50.00 10 GST @ 18% 54.00",
        "Current Bill Amount 3,004.00 Arrears/Advances 0.00 Current Interest/ Late Fees 0.00 "
        "Previous Interest/ Late Fees 0.00 Total Maintenance Payable Amount Rs. 3,004.00",
        "Notes * We recommend payment through NEFT, giving following details",
        "(a) Beneficiary Name: MB SOCIETY PDF1 CHS LTD",
        "(b) Account No: 123456789012 with IFSC Code: SRCB0000123",
        "(c) Bank: Saraswat Bank", "(d) UPI ID: mbsociety@sbi",
        "* Interest @ 21% p.a. will be charged on dues not paid by the due date (grace period 5 days).",
        "* Any queries related to the bill should be raised within 7 days of bill issuance",
        "* Outstanding dues are subject to final audit.",
        "* Parking stickers are issued at the office.",
        "This is a Computer Generated bill, hence no signature is required.",
    ]:
        assert expected in text, expected
    assert "Receipts: Towards" not in text      # the flat's first bill
    assert "Virtual A/c No." not in text        # the flat has none


def test_virtual_account_number_on_the_bill(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf5")
    flat1.virtual_account_number = "SHARA0101"
    db.commit()
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={
        "bank_account_name": "MB Society pdf5 CHS Ltd", "bank_account_number": "123456789012",
        "bank_ifsc": "SVCB0000045", "bank_name": "SVC Co-Op Bank Ltd",
    }, headers=manager["headers"])
    assert r.status_code == 200, r.text
    bill_id = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one().id

    _, text = _bill_pdf(db, bill_id)
    assert "Virtual A/c No.(VAN) : SHARA0101" in text
    # Members pay to the flat's VAN, not the society's account number
    assert "(b) Account No: Virtual Ac No Mentioned Above in Bill with IFSC Code: SVCB0000045" in text
    assert "123456789012" not in text


def test_member_fallback_and_own_payments_not_listed(client, db):
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
    assert "Name : Vik Mehta" in text
    # The foot lists receipts towards the previous bill only; this bill's
    # payment has its own receipt document.
    assert r.json()["receipt_number"] not in text and "Receipts: Towards" not in text


def test_arrears_interest_and_previous_bill_receipts(client, db):
    """Arrears print without the interest billed earlier and still unpaid,
    which shows as Previous Interest; the payments towards the previous bill
    are listed at the foot."""
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
    month = f"{first.cycle.cycle_start:%b-%Y}"
    for expected in [
        "Current Bill Amount 2,854.00 Arrears/Advances 854.00 Current Interest/ Late Fees 0.00 "
        "Previous Interest/ Late Fees 46.00 Total Maintenance Payable Amount Rs. 3,754.00",
        f"Receipts: Towards Bill No. {first.invoice_number} for {month}",
        "Receipt No. Date Amount Tra. Type Reference No. Cheque Bank Name Narration:",
        f"10763 28-Jul-26 2,000.00 CHEQUE 004512 UBI Maintenance paid for {month}",
    ]:
        assert expected in text, expected


def test_bill_payment_details_are_validated(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdf3")
    for field, bad in (("bank_ifsc", "SBI123"), ("upi_id", "no-at-sign"), ("bank_account_number", "12AB")):
        r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={field: bad},
                       headers=manager["headers"])
        assert r.status_code == 422, (field, r.text)
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={"upi_id": "  "},
                   headers=manager["headers"])
    assert r.status_code == 200 and r.json()["upi_id"] is None


# ── The member's name block: every owner on a line of their own, aligned, and inside the box ──────────────────

def _first_bill(client, db, tag):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, tag)
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    return society, flat1, bill


def test_each_owner_prints_on_a_line_of_their_own(client, db):
    from app.models.resident import ResidentType
    society, flat1, bill = _first_bill(client, db, "pdfn1")
    db.add(Resident(full_name="Vikram Rao", flat_id=flat1.id, resident_type=ResidentType.CO_OWNER))
    db.add(Resident(full_name="Tara Rao", flat_id=flat1.id, resident_type=ResidentType.FAMILY))
    db.commit()
    db.expire_all()
    _, text = _bill_pdf(db, bill.id)
    # the resident it was raised to first, then the other owner; a family member is not an owner, so not on the bill
    assert "Name : Asha Rao Vikram Rao Flat No. :" in text
    assert "Tara Rao" not in text


def test_a_name_entered_as_two_owners_is_split_onto_two_lines(client, db):
    society, flat1, bill = _first_bill(client, db, "pdfn2")
    bill.resident.full_name = "Nitin Baban Shendge & Jayashri Nitin Shendge"
    db.commit()
    db.expire_all()
    _, text = _bill_pdf(db, bill.id)
    assert "Name : Nitin Baban Shendge Jayashri Nitin Shendge Flat No. :" in text
    assert "&" not in text.split("Flat No.")[0]


def test_a_family_members_bill_carries_only_that_person(client, db):
    from app.models.resident import ResidentType
    society, flat1, bill = _first_bill(client, db, "pdfn3")
    tenant = Resident(full_name="Tara Rao", flat_id=flat1.id, resident_type=ResidentType.FAMILY)
    db.add(tenant)
    db.commit()
    bill.resident_id = tenant.id
    db.commit()
    db.expire_all()
    _, text = _bill_pdf(db, bill.id)
    assert "Name : Tara Rao Flat No. :" in text
    assert "Asha Rao" not in text


def test_the_details_box_keeps_each_column_inside_its_half(client, db):
    """A long name used to run past the left half and print over 'Bill No.'. Both halves are measured as laid out."""
    from reportlab.lib.pagesizes import A4
    from app.modules.billing.services.bill_pdf import PAGE_MARGINS, bill_story
    society, flat1, bill = _first_bill(client, db, "pdfn4")
    bill.resident.full_name = "Chandrashekhar Venkataraghavan Subramaniam & Lakshmi Narayanan Venkataraghavan Iyer"
    flat1.virtual_account_number = "SHARA0101"
    db.commit()
    db.expire_all()
    svc = BillingService(db)
    bill = svc.get_bill(bill.id)
    width = A4[0] - PAGE_MARGINS["leftMargin"] - PAGE_MARGINS["rightMargin"]
    story = bill_story(bill, svc.get_maintenance_settings(bill.society_id), width, **svc._bill_print_context(bill))
    box = next(f for f in story if getattr(f, "_cellvalues", None) and len(f._cellvalues[0]) == 2
               and hasattr(f._cellvalues[0][0], "_cellvalues"))
    left, right = box._cellvalues[0]
    inner = width * 0.5 - 18                         # a half, less the box's padding (12 left, 6 right)
    for table in (left, right):
        w, _ = table.wrap(width, 10_000)
        assert w <= inner + 0.01, (w, inner)
    # the two long names are two lines, the rest one line each: the left block is taller than the right
    assert left.wrap(width, 10_000)[1] > right.wrap(width, 10_000)[1]


# ── The classic layout ────────────────────────────────────────────────────────

def _classic(client, db, tag, **settings):
    """A society on the classic layout with its first bill issued: (society, flat1, manager, bill, cycle_id)."""
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, tag)
    r = client.put(f"/api/v1/billing/maintenance-settings/{society.id}",
                   json={"bill_layout": "classic", **settings}, headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["bill_layout"] == "classic"
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    return society, flat1, manager, bill, cycle_id


def test_the_layout_is_a_setting_standard_unless_chosen(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pdfl0")
    h = manager["headers"]
    assert client.get(f"/api/v1/billing/maintenance-settings/{society.id}", headers=h).json()["bill_layout"] == "standard"
    assert client.put(f"/api/v1/billing/maintenance-settings/{society.id}", json={"bill_layout": "fancy"},
                      headers=h).status_code == 422
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    _, text = _bill_pdf(db, bill.id)
    assert "Maintenance Bill" in text and "Notes *" in text.replace("Notes * ", "Notes *")   # the standard layout


def test_classic_layout_lists_every_head_and_the_totals(client, db):
    society, flat1, manager, bill, cycle_id = _classic(
        client, db, "pdfl1", bank_account_number="520101046817693", bank_ifsc="UBIN0904309", bank_name="Union Bank")
    society.registration_number = "BOM/WR/HSG/TC/10133/98-99"
    flat1.area_sqft = 437
    db.commit()
    db.expire_all()
    svc = BillingService(db)
    bill = svc.get_bill(bill.id)
    pdf = generate_maintenance_bill_pdf(bill, svc.get_maintenance_settings(bill.society_id), compress=False,
                                        **{**svc._bill_print_context(bill),
                                           "element_codes": {"Maintenance": "service_charges", "Water": "water_charges",
                                                             "Festival Fund": "other", "Legal Charges": "other"}})
    text = " ".join(_text(pdf).replace("|", " ").split())
    for expected in [
        "MB SOCIETY PDFL1", "Regn. No. BOM/WR/HSG/TC/10133/98-99",
        _bill_month(bill),                              # "Bill for the Period Oct-2026 to Nov-2026" for a 30-day cycle
        "Name : Asha Rao FLAT NO Tower A 101",
        f"Bill No. : {bill.invoice_number}", f"Bill Date : {bill.bill_date:%d/%m/%Y}",
        f"Due Date : {bill.due_date:%d/%m/%Y}", "Area Carpet : 437 Sq. Feet",
        "P a r t i c u l a r s Amount (in Rs.)",
        "Maintenance 2,500.00 Water 300.00",               # the heads as the society named them, not grouped
        "Festival Fund 0.00", "Legal Charges 0.00",         # heads not charged this time print 0.00
        "GST @ 18% 54.00",
        "Total : 2,854.00", "Arrears / Advance : 0.00", "Accumulated Interest : 0.00",
        "Interest on Principal Arrears of : 0.00", "Grand Total : 2,854.00",
        "Rs. Two Thousand Eight Hundred Fifty Four only.",
        "Notes :", "1. Interest @ 12% p.a.", "NEFT to MB SOCIETY PDFL1",
        "A/c No. 520101046817693", "IFSC UBIN0904309",
        "Outstanding dues are subject to final audit.",
        "HON. SECRETARY / TREASURER / CHAIRMAN",
    ]:
        assert expected in text, expected
    # the standard layout's own furniture is not there
    assert "Current Bill Amount" not in text and "Computer Generated" not in text


def test_classic_layout_prints_the_previous_bills_receipt_slip(client, db):
    society, flat1, manager, first, cycle_id = _classic(client, db, "pdfl2")
    db.add(PaymentReceipt(society_id=society.id, bill_id=first.id, flat_id=flat1.id, receipt_number="10905",
                          payment_date=date(2026, 9, 28), amount=Decimal("2000.00"),
                          payment_mode=PaymentMode.CHEQUE, cheque_number="130364410038", bank_name="HDFC BANK"))
    first.paid_amount = Decimal("2000.00")
    first.outstanding = first.total_amount - first.paid_amount
    db.commit()
    second_cycle = _cycle(client, manager["headers"], society.id, name="Nov 2026").json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{second_cycle}/generate-bills", headers=manager["headers"]).status_code == 200
    second = db.query(MaintenanceBill).filter_by(cycle_id=UUID(second_cycle), flat_id=flat1.id).one()
    _, text = _bill_pdf(db, second.id)
    for expected in [
        "RECEIPT for Previous Bill", "Receipt No.: 10905", "Date : 28/09/2026",
        "Received with thanks from Asha Rao", "Tower A 101",
        "Rs. Two Thousand only.", "Rs. 2,000.00",
        "Vide Cheque 130364410038 HDFC BANK", "Subject to realisation of cheque",
        f"Towards Bill No. {first.invoice_number} Dated : {first.bill_date:%d-%b-%Y}",
        "For MB SOCIETY PDFL2",
    ]:
        assert expected in text, expected
    # the flat's first bill has nothing to receipt
    _, first_text = _bill_pdf(db, first.id)
    assert "RECEIPT for Previous Bill" not in first_text


def test_classic_layout_puts_each_owner_on_a_line_and_in_the_box(client, db):
    society, flat1, manager, bill, cycle_id = _classic(client, db, "pdfl3")
    bill.resident.full_name = "Mukesh B. Ashar & Meena M. Ashar"
    db.commit()
    db.expire_all()
    _, text = _bill_pdf(db, bill.id)
    assert "Name : Mukesh B. Ashar Meena M. Ashar FLAT NO" in text


def test_classic_layout_in_the_bulk_print(client, db):
    from app.modules.billing.services.bill_pdf import generate_bills_pdf
    society, flat1, manager, bill, cycle_id = _classic(client, db, "pdfl4")
    svc = BillingService(db)
    bills = svc.list_cycle_bills(UUID(cycle_id))
    settings = svc.get_maintenance_settings(society.id)
    pdf = generate_bills_pdf([{"bill": b, "settings": settings, **svc._bill_print_context(b)} for b in bills],
                             title="t", author="a", compress=False)
    text = " ".join(_text(pdf).replace("|", " ").split())
    assert text.count("P a r t i c u l a r s") == len(bills) >= 2
