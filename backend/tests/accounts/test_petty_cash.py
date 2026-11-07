"""Petty cash kept as an imprest: topped up from the bank, spent a day at a time against expense heads, counted, and
read back as a day-wise book. Everything goes through the books."""
from datetime import timedelta

from app.utils.local_time import local_today, zone
from tests.billing.test_budget_suggestions import _rig
from tests.conftest import make_society, make_user

A = "/api/v1/accounts"
TODAY = local_today(zone(None))


def _ledgers(client, h, sid):
    r = client.get(f"{A}/ledgers/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _top_up(client, h, sid, amount, **extra):
    return client.post(f"{A}/petty-cash/top-up", headers=h, json={"society_id": str(sid), "amount": amount, **extra})


def _spend(client, h, sid, items, **extra):
    return client.post(f"{A}/petty-cash/expenses", headers=h, json={"society_id": str(sid), "items": items, **extra})


def _overview(client, h, sid):
    r = client.get(f"{A}/petty-cash/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _staff(db, society, admin_email="boss@pc.com"):
    """The manager enters, the admin approves: the usual two people."""
    who = make_user(db, admin_email, role="Society Admin")
    who["user"].society_id = society.id
    db.commit()
    return who["headers"]


def _rigged(db, tag):
    society, admin, manager, _ = _rig(db, tag)
    return society, admin, manager


def test_topping_up_and_spending_post_to_the_books_and_the_expense_heads(client, db):
    society, admin, manager = _rigged(db, "pc1")
    sid = society.id
    L = _ledgers(client, admin, sid)
    assert _overview(client, admin, sid)["balance"] == "0.00"

    t = _top_up(client, manager, sid, "5000", note="Monthly float")
    assert t.status_code == 201, t.text
    assert t.json()["voucher_type"] == "contra" and "Petty cash top-up" in t.json()["narration"]
    sides = {e["account_name"]: (e["debit"], e["credit"]) for e in t.json()["entries"]}
    assert sides["Petty Cash"][0] == "5000.00" and sides["Bank Account"][1] == "5000.00"
    assert _overview(client, admin, sid)["balance"] == "5000.00"

    r = _spend(client, manager, sid, [
        {"expense_account_id": L["office_expenses"]["id"], "amount": "450", "note": "Tea and biscuits"},
        {"expense_account_id": L["printing_stationery"]["id"], "amount": "250", "note": "Notice printing"}])
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["voucher_type"] == "payment" and v["amount"] == "700.00" and "Tea and biscuits" in v["narration"]
    sides = {e["account_name"]: (e["debit"], e["credit"]) for e in v["entries"]}
    assert sides["Office & General Expenses"][0] == "450.00" and sides["Printing & Stationery"][0] == "250.00"
    assert sides["Petty Cash"][1] == "700.00"

    # Waiting for the second person: not in the books yet, but already set aside so it can't be spent twice
    assert v["approval_status"] == "pending"
    o = _overview(client, admin, sid)
    assert (o["balance"], o["pending"], o["available"]) == ("5000.00", "700.00", "4300.00")

    approver = _staff(db, society)
    assert client.post(f"{A}/vouchers/{v['id']}/approve", json={}, headers=approver).status_code == 200
    o = _overview(client, admin, sid)
    assert (o["balance"], o["pending"], o["available"]) == ("4300.00", "0.00", "4300.00")
    assert o["spent_today"] == "700.00" and o["spent_month"] == "700.00"

    # Each head carries its own spend
    st = client.get(f"{A}/ledgers/{L['office_expenses']['id']}/statement", headers=admin).json()
    assert st["total_debit"] == "450.00"


def test_the_rules_keep_petty_cash_honest(client, db):
    society, admin, manager = _rigged(db, "pc2")
    sid = society.id
    L = _ledgers(client, admin, sid)
    head = L["office_expenses"]["id"]

    # Nothing in the box: nothing can be spent
    r = _spend(client, manager, sid, [{"expense_account_id": head, "amount": "100"}])
    assert r.status_code == 422 and "Top up petty cash" in r.json()["detail"]

    _top_up(client, manager, sid, "1000")
    r = _spend(client, manager, sid, [{"expense_account_id": head, "amount": "1500"}])
    assert r.status_code == 422 and "free to spend" in r.json()["detail"]
    # Only an expense head can be charged
    r = _spend(client, manager, sid, [{"expense_account_id": L["bank"]["id"], "amount": "100"}])
    assert r.status_code == 422 and "expense head" in r.json()["detail"]
    # No future date, no empty list
    tomorrow = str(TODAY + timedelta(days=2))
    assert _spend(client, manager, sid, [{"expense_account_id": head, "amount": "10"}],
                  voucher_date=tomorrow).status_code == 422
    assert _spend(client, manager, sid, []).status_code == 422
    assert _top_up(client, manager, sid, "10", voucher_date=tomorrow).status_code == 422
    assert _top_up(client, manager, sid, "0").status_code == 422

    # The limit for one expense (admin sets it; a manager can't)
    assert client.put(f"{A}/petty-cash/{sid}/settings", headers=manager, json={"expense_limit": "300"}).status_code == 403
    o = client.put(f"{A}/petty-cash/{sid}/settings", headers=admin,
                   json={"expense_limit": "300", "float_amount": "2000", "custodian_name": "  Ramesh  "}).json()
    assert (o["expense_limit"], o["float_amount"], o["custodian_name"]) == ("300.00", "2000.00", "Ramesh")
    assert o["top_up_needed"] == "1000.00"                                   # 2000 float less the 1000 in the box
    r = _spend(client, manager, sid, [{"expense_account_id": head, "amount": "301"}])
    assert r.status_code == 422 and "limit of Rs. 300.00" in r.json()["detail"]
    assert _spend(client, manager, sid, [{"expense_account_id": head, "amount": "300"}]).status_code == 201
    # Clearing the limit
    o = client.put(f"{A}/petty-cash/{sid}/settings", headers=admin, json={"expense_limit": None}).json()
    assert o["expense_limit"] is None and o["float_amount"] == "2000.00"


def test_counting_the_cash_and_the_day_wise_book(client, db):
    society, admin, manager = _rigged(db, "pc3")
    sid = society.id
    L = _ledgers(client, admin, sid)
    head = L["office_expenses"]["id"]
    approver = _staff(db, society, "boss3@pc.com")

    _top_up(client, manager, sid, "3000")
    v = _spend(client, manager, sid, [{"expense_account_id": head, "amount": "400", "note": "Bulbs"}]).json()
    client.post(f"{A}/vouchers/{v['id']}/approve", json={}, headers=approver)

    ok = client.post(f"{A}/petty-cash/counts", headers=manager, json={"society_id": str(sid), "counted_amount": "2600"})
    assert ok.status_code == 201 and ok.json()["state"] == "tallies" and ok.json()["difference"] == "0.00"
    short = client.post(f"{A}/petty-cash/counts", headers=manager,
                        json={"society_id": str(sid), "counted_amount": "2550", "note": "50 short"}).json()
    assert short["state"] == "short" and short["difference"] == "-50.00" and short["book"] == "2600.00"
    over = client.post(f"{A}/petty-cash/counts", headers=manager,
                       json={"society_id": str(sid), "counted_amount": "2700"}).json()
    assert over["state"] == "excess" and over["difference"] == "100.00"
    assert client.post(f"{A}/petty-cash/counts", headers=manager,
                       json={"society_id": str(sid), "counted_amount": "-1"}).status_code == 422
    counts = client.get(f"{A}/petty-cash/{sid}/counts", headers=manager).json()
    assert len(counts) == 3 and {c["state"] for c in counts} == {"tallies", "short", "excess"}
    assert _overview(client, admin, sid)["last_count"]["counted"] in ("2600.00", "2550.00", "2700.00")

    book = client.get(f"{A}/registers/petty_cash/{sid}", headers=manager).json()
    assert book["kind"] == "petty_cash" and book["title"] == "Petty Cash Book"
    assert len(book["rows"]) == 1                                            # one day, today
    row = book["rows"][0]
    assert (row["opening"], row["received"], row["spent"], row["closing"]) == ("0.00", "3000.00", "400.00", "2600.00")
    assert "Bulbs" in row["on"] and row["counted"] == "2700.00"              # the day's last count stands
    assert row["difference"] == "100.00"
    totals = {t["label"]: t["value"] for t in book["totals"]}
    assert totals["Received Rs."] == "3000.00" and totals["Spent Rs."] == "400.00" and totals["Closing Rs."] == "2600.00"
    assert totals["Counted in excess Rs."] == "100.00" and totals["Counted short Rs."] == "0.00"
    # Same book as a printout and a spreadsheet
    pdf = client.get(f"{A}/registers/petty_cash/{sid}", params={"format": "pdf"}, headers=manager)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    csv_ = client.get(f"{A}/registers/petty_cash/{sid}", params={"format": "csv"}, headers=manager)
    assert csv_.status_code == 200 and "Bulbs" in csv_.text
    # Another period: nothing happened then
    old = client.get(f"{A}/registers/petty_cash/{sid}", headers=manager,
                     params={"date_from": str(TODAY - timedelta(days=60)), "date_to": str(TODAY - timedelta(days=40))}).json()
    assert old["rows"] == [] and old["totals"][0]["value"] == "0.00"


def test_each_societys_petty_cash_is_its_own(client, db):
    society, admin, manager = _rigged(db, "pc4")
    other = make_society(db, "Other Petty Society")
    _top_up(client, manager, society.id, "1000")
    outsider = make_user(db, "boss@other-pc.com", role="Society Admin")
    outsider["user"].society_id = other.id
    db.commit()
    assert client.get(f"{A}/petty-cash/{society.id}", headers=outsider["headers"]).status_code in (403, 404)
    assert _top_up(client, outsider["headers"], society.id, "100").status_code in (403, 404)
    assert _overview(client, outsider["headers"], other.id)["balance"] == "0.00"
