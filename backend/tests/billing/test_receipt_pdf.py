"""Payment receipts — a document of their own, never part of the maintenance
bill: receipt no. and date, member and flat, amount in words and figures,
mode (cheque no. / reference and bank), what it was paid towards (a bill,
or on account), "Subject to Realisation of Cheque", and the sign-off."""
import re
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.billing.models.billing import MaintenanceBill, PaymentMode, PaymentReceipt
from app.modules.billing.services.billing_service import BillingService
from app.modules.billing.services.receipt_pdf import generate_payment_receipt_pdf
from tests.billing.test_maintenance_billing import _generated_cycle


def _text(pdf: bytes) -> str:
    runs = re.findall(rb"\((.*?)\) Tj", pdf)
    text = " ".join(r.decode("latin1").replace("\\(", "(").replace("\\)", ")") for r in runs)
    return " ".join(text.split())


def _receipt_text(db, receipt_number):
    payment = BillingService(db).get_payment_by_receipt_number(receipt_number)
    return _text(generate_payment_receipt_pdf(payment, compress=False))


def _record(client, headers, flat_id, **extra):
    data = {"flat_id": str(flat_id), "amount": "2854.00", "payment_date": "2026-07-28",
            "payment_mode": "cash", **extra}
    r = client.post("/api/v1/billing/online-payments", data=data, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_receipt_on_billing_by_cheque(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "rc1")
    society.registration_number = "BOM/WR/HSG/TC/10133/98-99"
    db.commit()
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    rec = _record(client, manager["headers"], flat1.id, bill_id=str(bill.id), payment_mode="cheque",
                  transaction_ref="004512", bank_name="UBI, Dahisar (E)")

    text = _receipt_text(db, rec["receipt_number"])
    for expected in [
        "MB SOCIETY RC1", "Regn. No. BOM/WR/HSG/TC/10133/98-99",
        f"Receipt No.: {rec['receipt_number']} RECEIPT ON BILLING Date : 28/07/2026",
        "Received with thanks from ASHA RAO Tower A 101",
        "Rs. Two Thousand Eight Hundred Fifty Four only.",
        "Vide Cash/Chq. Cheque No. 004512, UBI, Dahisar (E) Rs. 2,854.00",
        f"Towards Bill No. {bill.invoice_number} Dated : {bill.bill_date:%d/%m/%Y}",
        "Subject to Realisation of Cheque",
        "For MB SOCIETY RC1", "HON. SECRETARY / TREASURER / CHAIRMAN",
    ]:
        assert expected in text, expected


def test_receipt_on_account(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "rc2")
    rec = _record(client, manager["headers"], flat2.id, amount="1500.00", purpose="parking")
    text = _receipt_text(db, rec["receipt_number"])
    for expected in ["RECEIPT ON ACCOUNT", "Received with thanks from VIK MEHTA Tower A 102",
                     "Rs. One Thousand Five Hundred only.", "Vide Cash/Chq. Cash Rs. 1,500.00",
                     "On Account of Parking Charges, to be adjusted against the member's bills."]:
        assert expected in text, expected
    assert "Towards Bill" not in text and "Subject to Realisation" not in text


def test_returned_cheque_receipt_prints_cancelled(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "rc3")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    db.add(PaymentReceipt(society_id=society.id, bill_id=bill.id, flat_id=flat1.id, receipt_number="RC3-1",
                          payment_date=date(2026, 7, 28), amount=Decimal("2854.00"),
                          payment_mode=PaymentMode.CHEQUE, cheque_number="7788", bank_name="SBI",
                          is_reversed=True, reversed_reason="Cheque returned unpaid"))
    db.commit()
    text = _receipt_text(db, "RC3-1")
    assert "Cheque No. 7788, SBI" in text and "CANCELLED: Cheque returned unpaid" in text


def test_receipt_download_is_limited_to_the_flat(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "rc4")
    rec = _record(client, manager["headers"], flat1.id)
    url = f"/api/v1/billing/receipts/{rec['receipt_number']}/pdf"
    for who, code in ((manager, 200), (resident, 200), (other, 404)):
        r = client.get(url, headers=who["headers"])
        assert r.status_code == code, (who, r.text)
    r = client.get(url, headers=resident["headers"])
    assert r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    assert client.get("/api/v1/billing/receipts/NOPE-1/pdf", headers=manager["headers"]).status_code == 404
