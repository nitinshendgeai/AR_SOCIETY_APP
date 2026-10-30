"""Vendor bill → payment → books. A bill booked for a vendor is a payable; it is settled by paying it (one bill, or
several in one cheque) from a chosen bank or cash ledger, never by a loose voucher that would leave the bill unpaid;
a wrongly entered bill can be cancelled while nothing has been paid on it."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.vendor.models.vendor import VendorInvoice
from tests.vendor.test_vendor_tds import V, _bill, _lines, _pay, _vendor, rig  # noqa: F401

A = "/api/v1/accounts"


def _ledgers(client, rig):
    r = client.get(f"{A}/ledgers/{rig['sid']}", headers=rig["admin"])
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _balance(client, rig, ledger_id):
    r = client.get(f"{A}/ledgers/{ledger_id}/statement", headers=rig["admin"])
    assert r.status_code == 200, r.text
    closing = r.json()["closing_dr_cr"]
    return Decimal(closing["amount"]) * (1 if closing["type"] == "Dr" else -1)


def _payables(client, rig):
    r = client.get(f"{A}/outstanding/{rig['sid']}", params={"kind": "payable"}, headers=rig["admin"])
    assert r.status_code == 200, r.text
    return r.json()


def _pay_bills(client, rig, vendor_id, items, expect=200, mode="neft", **extra):
    body = {"items": [{"invoice_id": i, "amount": str(a)} for i, a in items], "paid_date": str(date.today()),
            "payment_mode": mode, "payment_ref": "UTR-77", **extra}
    r = client.post(f"{V}/invoices/vendor/{vendor_id}/pay", headers=rig["manager"], json=body)
    assert r.status_code == expect, r.text
    return r.json()


def _second_bank(client, rig, L):
    r = client.post(f"{A}/ledgers", headers=rig["admin"], json={
        "society_id": rig["sid"], "group_id": L["bank"]["group_id"], "name": "HDFC Current", "is_bank": True})
    assert r.status_code == 201, r.text
    return r.json()


def test_the_open_bills_of_a_vendor_are_what_can_still_be_paid(client, rig):
    v = _vendor(client, rig)
    late = _bill(client, rig, v["id"], "10000", number="B-2", on=date.today() - timedelta(days=5),
                 due_date=str(date.today() - timedelta(days=1)))
    early = _bill(client, rig, v["id"], "5000", number="B-1", on=date.today() - timedelta(days=40),
                  due_date=str(date.today() - timedelta(days=10)))
    paid = _bill(client, rig, v["id"], "700", number="B-3")
    _pay(client, rig, paid["id"], "700")
    r = client.get(f"{V}/invoices/vendor/{v['id']}/open", headers=rig["manager"])
    assert r.status_code == 200, r.text
    got = r.json()
    assert [b["invoice_number"] for b in got["bills"]] == ["B-1", "B-2"]                      # oldest due first
    assert got["bills"][0]["days_overdue"] == 10 and got["total_outstanding"] == "15000.00"
    assert {b["invoice_id"] for b in got["bills"]} == {early["id"], late["id"]}


def test_a_bills_own_tds_is_not_payable_to_the_vendor(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "10000")
    held = rig["db"].query(VendorInvoice).filter(VendorInvoice.id == UUID(bill["id"])).one()
    held.tds_amount = Decimal("1000.00")                              # TDS deducted when the bill was booked
    rig["db"].commit()
    bill = client.get(f"{V}/invoices/{bill['id']}", headers=rig["manager"]).json()
    assert bill["tds_amount"] == "1000.00" and bill["outstanding"] == "9000.00"
    open_bills = client.get(f"{V}/invoices/vendor/{v['id']}/open", headers=rig["manager"]).json()
    assert open_bills["bills"][0]["outstanding"] == "9000.00"
    paid = _pay(client, rig, bill["id"], "9000")
    assert paid["is_paid"] and paid["outstanding"] == "0.00"
    assert client.get(f"{V}/invoices/vendor/{v['id']}/open", headers=rig["manager"]).json()["bills"] == []


def test_one_cheque_settles_several_bills_and_the_books_agree(client, rig):
    v = _vendor(client, rig, constitution="individual_proprietor", pan_number="ABCPE1234F")
    one = _bill(client, rig, v["id"], "10000", number="B-1", on=date.today() - timedelta(days=30))
    two = _bill(client, rig, v["id"], "4000", number="B-2", on=date.today() - timedelta(days=3))
    L = _ledgers(client, rig)
    assert _balance(client, rig, L["sundry_creditors"]["id"]) == Decimal("-14000")
    assert _payables(client, rig)["totals"]["outstanding"] == "14000.00"

    done = _pay_bills(client, rig, v["id"], [(one["id"], "10000"), (two["id"], "1500")])
    assert done["bills_paid"] == 2 and done["settled"] == "11500.00"
    assert done["paid_to_vendor"] == str(Decimal("11500.00") - Decimal(done["tds_held"]))
    shown = {i["invoice_number"]: i for i in client.get(f"{V}/invoices/vendor/{v['id']}", headers=rig["manager"]).json()}
    assert shown["B-1"]["is_paid"] and shown["B-1"]["outstanding"] == "0.00"
    assert not shown["B-2"]["is_paid"] and shown["B-2"]["outstanding"] == "2500.00"       # part paid
    # The vendor ledger, the payables report and the open bills all say ₹2,500
    assert _balance(client, rig, L["sundry_creditors"]["id"]) == Decimal("-2500")
    assert _payables(client, rig)["totals"]["outstanding"] == "2500.00"
    assert client.get(f"{V}/invoices/vendor/{v['id']}/open", headers=rig["manager"]).json()["total_outstanding"] == "2500.00"


def test_the_payment_is_made_from_the_chosen_bank_and_shows_on_its_reconciliation(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "3000", number="B-1", on=date.today() - timedelta(days=2))
    L = _ledgers(client, rig)
    hdfc = _second_bank(client, rig, L)
    _pay_bills(client, rig, v["id"], [(bill["id"], "3000")], bank_account_id=hdfc["id"])
    assert _balance(client, rig, hdfc["id"]) == Decimal("-3000")             # under the TDS limit: nothing held
    assert _balance(client, rig, L["bank"]["id"]) == Decimal("0")
    brs = client.get(f"{A}/bank-reconciliation/{rig['sid']}", params={"account_id": hdfc["id"]},
                     headers=rig["admin"]).json()
    assert [p["amount"] for p in brs["payments_not_cleared"]] == ["3000.00"]


def test_the_ledger_must_suit_the_way_it_is_paid(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "1000", number="B-1")
    L = _ledgers(client, rig)
    r = _pay_bills(client, rig, v["id"], [(bill["id"], "1000")], expect=422, bank_account_id=L["cash"]["id"])
    assert "cash" in r["detail"].lower()
    r = _pay_bills(client, rig, v["id"], [(bill["id"], "1000")], expect=422, mode="cash",
                   bank_account_id=L["bank"]["id"])
    assert "cash" in r["detail"].lower()
    r = _pay_bills(client, rig, v["id"], [(bill["id"], "1000")], expect=422, bank_account_id=L["audit_fees"]["id"])
    assert "cash or bank" in r["detail"].lower()
    ok = _pay_bills(client, rig, v["id"], [(bill["id"], "1000")], mode="cash", bank_account_id=L["cash"]["id"])
    assert ok["bills_paid"] == 1 and _balance(client, rig, L["cash"]["id"]) == Decimal("-1000")


def test_paying_several_bills_is_all_or_nothing(client, rig):
    v = _vendor(client, rig)
    one = _bill(client, rig, v["id"], "1000", number="B-1")
    two = _bill(client, rig, v["id"], "2000", number="B-2")
    r = _pay_bills(client, rig, v["id"], [(one["id"], "1000"), (two["id"], "9999")], expect=422)
    assert "exceeds" in r["detail"]
    shown = client.get(f"{V}/invoices/vendor/{v['id']}", headers=rig["manager"]).json()
    assert not any(i["is_paid"] or Decimal(i["paid_amount"]) for i in shown)
    assert _payables(client, rig)["totals"]["outstanding"] == "3000.00"
    _pay_bills(client, rig, v["id"], [(one["id"], "1"), (one["id"], "2")], expect=422)         # the same bill twice
    other = _vendor(client, rig, "Another Vendor", mobile="9876543299")
    stranger = _bill(client, rig, other["id"], "500", number="X-1")
    _pay_bills(client, rig, v["id"], [(stranger["id"], "500")], expect=422)                      # not this vendor's
    _pay_bills(client, rig, v["id"], [], expect=422)


def test_a_loose_payment_voucher_cannot_settle_a_billed_vendor(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "5000", number="B-1")
    L = _ledgers(client, rig)

    def voucher(vendor_id, amount="5000", expect=201):
        r = client.post(f"{A}/vouchers", headers=rig["admin"], json={
            "society_id": rig["sid"], "voucher_type": "payment", "voucher_date": str(date.today()),
            "entries": [{"account_id": L["sundry_creditors"]["id"], "debit": amount,
                         **({"vendor_id": vendor_id} if vendor_id else {})},
                        {"account_id": L["bank"]["id"], "credit": amount}]})
        assert r.status_code == expect, r.text
        return r.json()

    assert "vendor" in voucher(None, expect=422)["detail"].lower()              # the payable is kept vendor by vendor
    blocked = voucher(v["id"], expect=422)["detail"]
    assert "Sparkle Services" in blocked and "bills" in blocked
    _pay_bills(client, rig, v["id"], [(bill["id"], "5000")])
    assert voucher(v["id"], "800")["amount"] == "800.00"                         # nothing outstanding: an advance


def test_a_wrongly_entered_bill_can_be_cancelled_until_it_is_paid(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "5000", number="B-1")
    L = _ledgers(client, rig)
    assert _balance(client, rig, L["sundry_creditors"]["id"]) == Decimal("-5000")

    assert client.post(f"{V}/invoices/{bill['id']}/cancel", json={"reason": "Wrong vendor"},
                       headers=rig["manager"]).status_code == 403                       # a manager enters, the committee cancels
    paid = _pay(client, rig, bill["id"], "5000")
    blocked = client.post(f"{V}/invoices/{bill['id']}/cancel", json={"reason": "Wrong vendor"}, headers=rig["admin"])
    assert blocked.status_code == 409 and "reverse" in blocked.json()["detail"]
    reverse = client.post(f"{V}/payments/{paid['payments'][0]['id']}/reverse", json={"reason": "Bounced"},
                          headers=rig["manager"])
    assert reverse.status_code == 200, reverse.text

    gone = client.post(f"{V}/invoices/{bill['id']}/cancel", json={"reason": "Wrong vendor"}, headers=rig["admin"])
    assert gone.status_code == 200 and gone.json()["is_cancelled"]
    assert _balance(client, rig, L["sundry_creditors"]["id"]) == Decimal("0")        # out of the books …
    assert _payables(client, rig)["totals"]["outstanding"] == "0.00"                  # … and the payables
    assert client.get(f"{V}/invoices/vendor/{v['id']}/open", headers=rig["manager"]).json()["bills"] == []
    assert client.get(f"{V}/invoices/vendor/{v['id']}", headers=rig["manager"]).json() == []
    assert client.post(f"{V}/invoices/{bill['id']}/cancel", json={"reason": "again"},
                       headers=rig["admin"]).status_code == 409
    assert _pay(client, rig, bill["id"], "1", expect=409)["detail"] == "Invoice was cancelled"
    # The same number can be entered again, correctly
    again = _bill(client, rig, v["id"], "4000", number="B-1")
    assert again["outstanding"] == "4000.00"
    register = client.get(f"{A}/registers/bills/{rig['sid']}", headers=rig["admin"]).json()
    states = {r["invoice_id"]: r["status"] for r in register["rows"]}
    assert states[bill["id"]] == "cancelled" and states[again["id"]] == "unpaid"
    assert register["totals"]["count"] == 1 and register["totals"]["outstanding"] == "4000.00"


def test_a_paid_bill_is_cancelled_in_one_step_by_reversing_its_payments(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "5000", number="B-9")
    L = _ledgers(client, rig)
    bank_before = _balance(client, rig, L["bank"]["id"])
    _pay(client, rig, bill["id"], "3000")
    paid = _pay(client, rig, bill["id"], "2000")
    assert paid["is_paid"] and len(paid["payments"]) == 2
    assert _balance(client, rig, L["bank"]["id"]) == bank_before - Decimal("5000")

    url = f"{V}/invoices/{bill['id']}/cancel"
    assert client.post(url, json={"reason": "Wrong vendor", "reverse_payments": True},
                       headers=rig["manager"]).status_code == 403                       # the committee decides
    assert client.post(url, json={"reason": "Wrong vendor"}, headers=rig["admin"]).status_code == 409   # as before

    done = client.post(url, json={"reason": "Wrong vendor", "reverse_payments": True}, headers=rig["admin"])
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["is_cancelled"] and body["paid_amount"] == "0.00" and not body["is_paid"]
    assert all(p["is_reversed"] and "Wrong vendor" in p["reversal_reason"] for p in body["payments"])
    # the books are back as they were: the money is in the bank again and nothing is owed or spent
    assert _balance(client, rig, L["bank"]["id"]) == bank_before
    assert _balance(client, rig, L["sundry_creditors"]["id"]) == Decimal("0")
    assert client.post(url, json={"reason": "Again", "reverse_payments": True},
                       headers=rig["admin"]).status_code == 409                        # already cancelled


def test_one_step_cancel_of_an_unpaid_bill_needs_no_reversal(client, rig):
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "1200", number="B-10")
    r = client.post(f"{V}/invoices/{bill['id']}/cancel", json={"reason": "Duplicate", "reverse_payments": True},
                    headers=rig["admin"])
    assert r.status_code == 200 and r.json()["is_cancelled"]


def test_post_now_says_what_could_not_be_posted_and_why(client, rig, monkeypatch):
    from app.modules.accounts.services.postings import AccountPostings
    real = AccountPostings.post_vendor_invoice

    def broken(self, inv, user=None):
        raise ValueError("Vendor invoice GST component total must equal GST amount")

    monkeypatch.setattr(AccountPostings, "post_vendor_invoice", broken)
    v = _vendor(client, rig)
    bill = _bill(client, rig, v["id"], "5000", number="B-STUCK")           # the books refuse it: it stays unposted
    summary = lambda: client.get(f"{A}/summary/{rig['sid']}", headers=rig["admin"]).json()
    assert summary()["pending_postings"] == 1

    r = client.post(f"{A}/sync/{rig['sid']}", headers=rig["admin"])
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["total"] == 1 and got["failed"] == 1                         # tried one, none went in
    assert got["errors"][0]["type"] == "Vendor bill" and got["errors"][0]["number"] == "B-STUCK"
    assert got["errors"][0]["vendor"] and "GST component" in got["errors"][0]["message"]
    assert summary()["pending_postings"] == 1                              # still on the list

    monkeypatch.setattr(AccountPostings, "post_vendor_invoice", real)       # the cause is fixed
    r = client.post(f"{A}/sync/{rig['sid']}", headers=rig["admin"])
    assert r.json()["total"] == 1 and r.json()["failed"] == 0 and r.json()["errors"] == []
    assert summary()["pending_postings"] == 0
