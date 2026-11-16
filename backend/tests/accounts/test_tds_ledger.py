"""The TDS ledger report: what is still to be deposited with the government and what can be claimed back, read from
the two TDS ledgers without changing them."""
from decimal import Decimal

from tests.accounts.test_accounts import _ledgers
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user, place_in

A = "/api/v1/accounts"


def _post(client, admin, sid, vtype, day, dr, cr, amount, narration):
    v = client.post(f"{A}/vouchers", headers=admin["headers"], json={
        "society_id": sid, "voucher_type": vtype, "voucher_date": day, "narration": narration,
        "entries": [{"account_id": dr["id"], "debit": amount}, {"account_id": cr["id"], "credit": amount}]})
    assert v.status_code == 201, v.text
    if v.json()["approval_status"] != "approved":
        assert client.post(f"{A}/vouchers/{v.json()['id']}/approve", json={"note": "ok"},
                           headers=admin["headers"]).status_code == 200


def test_tds_ledger_shows_what_to_pay_and_what_to_receive(client, db):
    society, *_, manager, _res, _other = _rig(db, "tl1")
    admin = make_user(db, "admin@tl1.com", role="Society Admin", full_name="Asha Admin")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)

    # 2,000 held back from a vendor in the first quarter, 500 more in the second; 1,200 deposited since.
    _post(client, admin, sid, "journal", "2026-05-10", L["security_charges"], L["tds_payable"], "2000", "TDS on guard agency")
    _post(client, admin, sid, "journal", "2026-08-10", L["security_charges"], L["tds_payable"], "500", "TDS on plumber")
    _post(client, admin, sid, "payment", "2026-07-07", L["tds_payable"], L["cash"], "1200", "TDS deposited, challan")
    # 90 deducted by the bank from FD interest
    _post(client, admin, sid, "journal", "2026-06-30", L["tds_receivable"], L["interest_fd"], "90", "Bank TDS on FD interest")

    r = client.get(f"{A}/tds-ledger/{sid}", params={"date_from": "2026-04-01", "date_to": "2026-09-30"}, headers=h)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["to_pay"] == "1300.00" and rep["excess_deposited"] == "0.00"
    assert rep["to_receive"] == "90.00"

    q = {x["quarter"]: x for x in rep["payable_quarters"]}
    assert q["Q1 Apr–Jun 2026-27"]["credit"] == "2000.00" and q["Q1 Apr–Jun 2026-27"]["debit"] == "0.00"
    assert q["Q2 Jul–Sep 2026-27"]["credit"] == "500.00" and q["Q2 Jul–Sep 2026-27"]["debit"] == "1200.00"
    assert [l["voucher_number"] for l in rep["payable"]["lines"]] and len(rep["payable"]["lines"]) == 3
    assert rep["payable"]["closing"] == {"amount": "1300.00", "type": "Cr"}
    assert rep["receivable"]["closing"] == {"amount": "90.00", "type": "Dr"}

    # Money paid in before the period still counts: the opening balance carries it
    later = client.get(f"{A}/tds-ledger/{sid}", params={"date_from": "2026-07-01", "date_to": "2026-09-30"}, headers=h).json()
    assert later["to_pay"] == "1300.00" and later["payable"]["opening"] == {"amount": "2000.00", "type": "Cr"}

    pdf = client.get(f"{A}/tds-ledger/{sid}", params={"date_from": "2026-04-01", "date_to": "2026-09-30", "format": "pdf"}, headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_tds_deposited_more_than_deducted_is_shown_as_excess(client, db):
    society, *_, manager, _res, _other = _rig(db, "tl2")
    admin = make_user(db, "admin@tl2.com", role="Society Admin")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    _post(client, admin, sid, "journal", "2026-05-10", L["security_charges"], L["tds_payable"], "100", "TDS")
    _post(client, admin, sid, "payment", "2026-06-07", L["tds_payable"], L["cash"], "150", "Deposited")
    rep = client.get(f"{A}/tds-ledger/{sid}", params={"date_from": "2026-04-01", "date_to": "2026-06-30"}, headers=h).json()
    assert rep["to_pay"] == "0.00" and rep["excess_deposited"] == "50.00"


def test_tds_ledger_rejects_a_backwards_period_and_other_societies(client, db):
    society, *_, manager, _res, _other = _rig(db, "tl3")
    other, *_, other_manager, _r, _o = _rig(db, "tl4")
    place_in(db, manager, society)                       # a society's own manager, not a platform-wide one
    h, sid = manager["headers"], str(society.id)
    assert client.get(f"{A}/tds-ledger/{sid}", params={"date_from": "2026-09-01", "date_to": "2026-04-01"}, headers=h).status_code == 422
    assert client.get(f"{A}/tds-ledger/{other.id}", headers=h).status_code == 403
    assert client.get(f"{A}/tds-ledger/{sid}", headers=h).status_code == 200            # defaults to the current year
