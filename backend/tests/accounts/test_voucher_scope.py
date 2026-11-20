"""Members' vouchers and the society's own are told apart: the Day Book can show only what concerns the residents' flats
(their bills, what they paid, an entry an accountant makes against a flat) or only what the society itself spends and holds."""
from tests.accounts.test_accounts import API, _issued_bills, _ledgers


def _post(client, h, sid, vtype, entries, day="2026-09-15", **extra):
    r = client.post(f"{API}/vouchers", json={
        "society_id": sid, "voucher_type": vtype, "voucher_date": day, "entries": entries, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _list(client, h, sid, **params):
    r = client.get(f"{API}/vouchers/society/{sid}", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_members_vouchers_and_the_societys_own_are_told_apart(client, db):
    society, flat1, _flat2, manager, _res, _bill = _issued_bills(client, db, "scope1")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    paid = _post(client, h, sid, "payment", [{"account_id": L["electricity"]["id"], "debit": "8450"},
                                              {"account_id": L["bank"]["id"], "credit": "8450"}])
    interest = _post(client, h, sid, "receipt", [{"account_id": L["bank"]["id"], "debit": "700"},
                                                  {"account_id": L["interest_sb"]["id"], "credit": "700"}])
    # entered by hand, but against a flat: a waiver
    waiver = _post(client, h, sid, "journal", [{"account_id": L["fines_penalties"]["id"], "debit": "50"},
                                                {"account_id": L["members_dues"]["id"], "credit": "50",
                                                 "flat_id": str(flat1.id)}], day="2026-09-16")
    everything = _list(client, h, sid)
    mine = _list(client, h, sid, scope="members")
    society_own = _list(client, h, sid, scope="society")

    by_id = {v["id"]: v for v in everything}
    assert by_id[paid["id"]]["scope"] == "society" and by_id[interest["id"]]["scope"] == "society"
    assert by_id[waiver["id"]]["scope"] == "members"
    assert all(v["scope"] == "members" for v in mine) and all(v["scope"] == "society" for v in society_own)
    assert {v["id"] for v in mine} | {v["id"] for v in society_own} == set(by_id)          # nothing in neither
    assert not ({v["id"] for v in mine} & {v["id"] for v in society_own})                  # nothing in both
    assert waiver["id"] in {v["id"] for v in mine}
    assert {paid["id"], interest["id"]} <= {v["id"] for v in society_own}
    # the maintenance bills the app posted for the flats are the members'
    bills = [v for v in everything if v["source_type"] == "maintenance_bill"]
    assert bills and all(v["scope"] == "members" for v in bills)
    assert all(v["id"] in {m["id"] for m in mine} for v in bills)


def test_scope_works_with_the_other_filters_and_on_the_printed_day_book(client, db):
    society, flat1, _f2, manager, _res, _bill = _issued_bills(client, db, "scope2")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    _post(client, h, sid, "payment", [{"account_id": L["electricity"]["id"], "debit": "100"},
                                       {"account_id": L["cash"]["id"], "credit": "100"}])
    _post(client, h, sid, "journal", [{"account_id": L["fines_penalties"]["id"], "debit": "50"},
                                       {"account_id": L["members_dues"]["id"], "credit": "50", "flat_id": str(flat1.id)}])
    # type and scope together
    assert [v["voucher_type"] for v in _list(client, h, sid, scope="members", voucher_type="journal")] == ["journal"]
    assert _list(client, h, sid, scope="society", voucher_type="journal") == []
    assert [v["voucher_type"] for v in _list(client, h, sid, scope="society", voucher_type="payment")] == ["payment"]
    assert _list(client, h, sid, scope="members", voucher_type="payment") == []
    assert client.get(f"{API}/day-book/{sid}/pdf", params={"scope": "members"}, headers=h).status_code == 200
    assert client.get(f"{API}/day-book/{sid}/pdf", params={"scope": "society"}, headers=h).status_code == 200


def test_an_unknown_scope_is_refused(client, db):
    society, *_rest, manager, _res, _bill = _issued_bills(client, db, "scope3")
    r = client.get(f"{API}/vouchers/society/{society.id}", params={"scope": "everyone"}, headers=manager["headers"])
    assert r.status_code == 422
