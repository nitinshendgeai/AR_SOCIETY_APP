"""Correcting a voucher the society entered (the earlier version kept on
record), and the books' printed documents: a voucher, a ledger account, the
day book and the members' ledger."""
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher, VoucherRevision
from tests.accounts.test_accounts import _balance, _issued_bills
from tests.accounts.test_reports import _books, _ledgers, _voucher
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

API = "/api/v1/accounts"


def _payment(client, h, sid, L, amount="8450", d="2026-09-15", approver=None):
    return _voucher(client, h, sid, "payment", d, [
        {"account_id": L["electricity"]["id"], "debit": amount},
        {"account_id": L["bank"]["id"], "credit": amount}], approver=approver)


def _edit(client, h, vid, d, entries, reason="Typed the wrong amount", expect=200, approver=None, **extra):
    """Edit a voucher. An edited payment or journal goes back for approval, so it is approved again when an
    approver is given (the manager who edits cannot approve)."""
    r = client.put(f"{API}/vouchers/{vid}", json={"voucher_date": d, "entries": entries, "reason": reason, **extra},
                   headers=h)
    assert r.status_code == expect, r.text
    out = r.json()
    if expect == 200 and approver and out.get("approval_status") == "pending":
        ok = client.post(f"{API}/vouchers/{vid}/approve", json={"note": "Approved"}, headers=approver["headers"])
        assert ok.status_code == 200, ok.text
        out = ok.json() if "revisions" in ok.json() else out
    return out


def test_edit_voucher_keeps_number_and_earlier_version(client, db):
    society, *_, manager, _res, _other = _rig(db, "ve1")
    h, sid = manager["headers"], str(society.id)
    approver = make_user(db, "approver@ve1.com", role="Society Admin")
    L = _ledgers(client, h, sid)
    v = _payment(client, h, sid, L, approver=approver)
    assert v["revisions"] == [] and v["edited_at"] is None

    out = _edit(client, h, v["id"], "2026-09-16", [
        {"account_id": L["electricity"]["id"], "debit": "8540"},
        {"account_id": L["bank"]["id"], "credit": "8540"}], narration="MSEDCL Aug-2026", reference="CHQ 124", approver=approver)
    assert out["voucher_number"] == "PV/2026-27/0001" and out["amount"] == "8540.00"
    assert out["voucher_date"] == "2026-09-16" and out["narration"] == "MSEDCL Aug-2026"
    assert out["edited_by_name"] and out["edited_at"]
    [rev] = out["revisions"]
    assert rev["revision_no"] == 1 and rev["reason"] == "Typed the wrong amount"
    assert rev["before"]["amount"] == "8450.00" and rev["before"]["voucher_date"] == "2026-09-15"
    assert [e["account_name"] for e in rev["before"]["entries"]] == [L["electricity"]["name"], L["bank"]["name"]]
    assert _balance(client, h, sid, "electricity") == Decimal("8540")
    assert _balance(client, h, sid, "bank") == Decimal("-8540")

    # Split across two expense heads; the newest earlier version is listed first
    out = _edit(client, h, v["id"], "2026-09-16", [
        {"account_id": L["electricity"]["id"], "debit": "8000"},
        {"account_id": L["audit_fees"]["id"], "debit": "540"},
        {"account_id": L["bank"]["id"], "credit": "8540"}], reason="Split the audit fee out", approver=approver)
    assert [r["revision_no"] for r in out["revisions"]] == [2, 1]
    assert out["revisions"][0]["before"]["amount"] == "8540.00" and len(out["entries"]) == 3
    assert _balance(client, h, sid, "electricity") == Decimal("8000")
    assert db.query(VoucherRevision).filter_by(voucher_id=UUID(v["id"])).count() == 2

    # Moved into the next financial year: numbered in that year
    out = _edit(client, h, v["id"], "2027-04-02", [
        {"account_id": L["electricity"]["id"], "debit": "8540"},
        {"account_id": L["bank"]["id"], "credit": "8540"}], reason="Paid after year end", approver=approver)
    assert out["voucher_number"] == "PV/2027-28/0001" and out["fiscal_year"] == "2027-28"


def test_edit_follows_the_voucher_rules(client, db):
    society, flat1, _f2, manager, _res, _bill = _issued_bills(client, db, "ve2")
    h, sid = manager["headers"], str(society.id)
    approver = make_user(db, "approver@ve2.com", role="Society Admin")
    L = _ledgers(client, h, sid)
    v = _payment(client, h, sid, L, "500", approver=approver)
    ok = [{"account_id": L["electricity"]["id"], "debit": "600"}, {"account_id": L["bank"]["id"], "credit": "600"}]
    # A reason is needed; debits must equal credits; a payment stays a payment
    _edit(client, h, v["id"], "2026-09-15", ok, reason="", expect=422)
    _edit(client, h, v["id"], "2026-09-15", [ok[0], {**ok[1], "credit": "590"}], expect=422)
    _edit(client, h, v["id"], "2026-09-15", [
        {"account_id": L["bank"]["id"], "debit": "600"},
        {"account_id": L["misc_income"]["id"], "credit": "600"}], expect=422)
    # Members' Dues lines still name the flat
    r = _voucher(client, h, sid, "receipt", "2026-09-15", [
        {"account_id": L["cash"]["id"], "debit": "100"},
        {"account_id": L["members_dues"]["id"], "credit": "100", "flat_id": str(flat1.id)}])
    _edit(client, h, r["id"], "2026-09-15", [
        {"account_id": L["cash"]["id"], "debit": "100"},
        {"account_id": L["members_dues"]["id"], "credit": "100"}], expect=422)

    # Posted from a bill: edit the bill, not the voucher
    auto = db.query(Voucher).filter(Voucher.society_id == society.id, Voucher.source_type.isnot(None)).first()
    _edit(client, h, str(auto.id), str(auto.voucher_date), ok, expect=409)
    # Cancelled vouchers stay as they were
    assert client.post(f"{API}/vouchers/{v['id']}/cancel", json={"reason": "Duplicate"}, headers=h).status_code == 200
    _edit(client, h, v["id"], "2026-09-15", ok, expect=409)


def test_closed_year_vouchers_cant_be_edited(client, db):
    society, _flat, admin, _mgr, _res, L = _books(client, db, "ve3")
    h, sid = admin["headers"], str(society.id)
    v = db.query(Voucher).filter_by(society_id=society.id, voucher_type="payment").one()
    assert client.post(f"{API}/years/{sid}/2024-25/close", json={"reserve_pct": "0"}, headers=h).status_code == 200
    ok = [{"account_id": L["electricity"]["id"], "debit": "100"}, {"account_id": L["bank"]["id"], "credit": "100"}]
    _edit(client, h, str(v.id), "2025-01-10", ok, expect=409)
    # Nor can an open-year voucher be moved into the closed year
    open_v = _payment(client, h, sid, L, "100", d="2025-05-10")
    _edit(client, h, open_v["id"], "2025-03-10", ok, expect=409)


def test_printed_documents(client, db):
    society, flat1, _flat2, manager, resident, _bill = _issued_bills(client, db, "ve4")
    h, sid = manager["headers"], str(society.id)
    approver = make_user(db, "approver@ve4.com", role="Society Admin")
    L = _ledgers(client, h, sid)
    v = _payment(client, h, sid, L, approver=approver)
    _edit(client, h, v["id"], "2026-09-15", [
        {"account_id": L["electricity"]["id"], "debit": "8500"},
        {"account_id": L["bank"]["id"], "credit": "8500"}], approver=approver)
    client.post(f"{API}/vouchers/{_payment(client, h, sid, L, '50', approver=approver)['id']}/cancel", json={"reason": "Duplicate"},
                headers=h)

    def pdf(url, **params):
        r = client.get(url, params=params, headers=h)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
        return r

    r = pdf(f"{API}/vouchers/{v['id']}/pdf")
    assert "PV-2026-27-0001.pdf" in r.headers["content-disposition"]
    auto = db.query(Voucher).filter(Voucher.society_id == society.id, Voucher.voucher_type == "bill").first()
    pdf(f"{API}/vouchers/{auto.id}/pdf")
    pdf(f"{API}/ledgers/{L['bank']['id']}/statement", format="pdf", date_from="2026-04-01", date_to="2027-03-31")
    r = pdf(f"{API}/ledgers/{L['members_dues']['id']}/statement", format="pdf", flat_id=str(flat1.id))
    assert "Ledger-" in r.headers["content-disposition"]
    pdf(f"{API}/day-book/{sid}/pdf", date_from="2026-04-01", date_to="2027-03-31")
    pdf(f"{API}/day-book/{sid}/pdf", voucher_type="payment")
    pdf(f"{API}/members/{sid}", format="pdf")

    # The JSON answers are unchanged
    st = client.get(f"{API}/ledgers/{L['bank']['id']}/statement", headers=h).json()
    assert st["closing"] == "-8500.00"
    assert client.get(f"{API}/members/{sid}", headers=h).json()["members"]

    # Residents can't print the books
    rh = resident["headers"]
    assert client.get(f"{API}/vouchers/{v['id']}/pdf", headers=rh).status_code == 403
    assert client.get(f"{API}/day-book/{sid}/pdf", headers=rh).status_code == 403
    assert client.put(f"{API}/vouchers/{v['id']}", json={
        "voucher_date": "2026-09-15", "reason": "Not mine to change", "entries": [
            {"account_id": L["electricity"]["id"], "debit": "1"},
            {"account_id": L["bank"]["id"], "credit": "1"}]}, headers=rh).status_code == 403
