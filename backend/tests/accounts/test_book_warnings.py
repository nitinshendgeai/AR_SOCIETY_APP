"""Warnings on the Accounts page for things that are almost certainly a mistake: cash or bank in credit, and
opening balances that don't agree."""
from tests.accounts.test_accounts import API, _chart, _ledgers
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user


def _warnings(client, h, sid):
    r = client.get(f"{API}/summary/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return {w["code"]: w for w in r.json()["warnings"]}


def test_fresh_books_have_no_warnings(client, db):
    society, *_, manager, _res, _other = _rig(db, "bw1")
    assert _warnings(client, manager["headers"], str(society.id)) == {}


def test_cash_paid_out_before_any_opening_balance_warns(client, db):
    society, *_, manager, _res, _other = _rig(db, "bw2")
    approver = make_user(db, "admin@bw2.com", role="Society Admin")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    v = client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": "2026-09-15",
        "entries": [{"account_id": L["audit_fees"]["id"], "debit": "5000"},
                    {"account_id": L["cash"]["id"], "credit": "5000"}],
    }, headers=h).json()
    # Waiting for approval, the books haven't moved yet
    assert _warnings(client, h, sid) == {}
    assert client.post(f"{API}/vouchers/{v['id']}/approve", json={"note": "ok"},
                       headers=approver["headers"]).status_code == 200
    w = _warnings(client, h, sid)
    assert set(w) == {"negative_cash"}
    assert w["negative_cash"]["account_id"] == L["cash"]["id"]
    assert "₹5,000" in w["negative_cash"]["message"]

    # Entering the opening balance clears it
    r = client.patch(f"{API}/ledgers/{L['cash']['id']}",
                     json={"opening_balance": "20000", "opening_type": "dr"}, headers=h)
    assert r.status_code == 200, r.text
    # …but that opening balance has no matching credit, which is the second warning
    assert set(_warnings(client, h, sid)) == {"opening_unbalanced"}


def test_unbalanced_opening_balances_warn_until_matched(client, db):
    society, *_, manager, _res, _other = _rig(db, "bw3")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    assert client.patch(f"{API}/ledgers/{L['bank']['id']}",
                        json={"opening_balance": "100000", "opening_type": "dr"}, headers=h).status_code == 200
    w = _warnings(client, h, sid)
    assert set(w) == {"opening_unbalanced"}
    assert "₹1,00,000" in w["opening_unbalanced"]["message"]
    # Matching the other side (share capital / funds) balances the books
    funds = next(a for g in _chart(client, h, sid) for a in g["accounts"] if a["system_key"] == "sinking_fund")
    assert client.patch(f"{API}/ledgers/{funds['id']}",
                        json={"opening_balance": "100000", "opening_type": "cr"}, headers=h).status_code == 200
    assert _warnings(client, h, sid) == {}
