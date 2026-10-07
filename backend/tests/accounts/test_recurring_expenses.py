"""Recurring monthly expenses: templates that come up as due each month for a person to confirm, the payment
voucher a confirmation makes, skipping, and keeping each society's own."""
from datetime import date

from tests.billing.test_budget_suggestions import _rig
from tests.conftest import make_society, make_user

A = "/api/v1/accounts"
TODAY = date.today()


def _month(back: int) -> date:
    m = TODAY.month - 1 - back
    return date(TODAY.year + m // 12, m % 12 + 1, 1)


def _member(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who["headers"]


def _ledgers(client, h, sid):
    r = client.get(f"{A}/ledgers/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _make(client, h, sid, L, head="security_charges", **over):
    body = {"society_id": str(sid), "name": "Security agency", "expense_account_id": L[head]["id"],
            "amount": "30000", "day_of_month": 1, "start_month": str(_month(0)), "payee": "Shield Security", **over}
    r = client.post(f"{A}/recurring-expenses", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _due(client, h, sid):
    r = client.get(f"{A}/recurring-expenses/{sid}/due", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _record(client, h, rid, month, **body):
    return client.post(f"{A}/recurring-expenses/{rid}/record", headers=h, json={"month": str(month), **body})


def test_a_new_monthly_expense_comes_up_due_and_records_as_a_payment(client, db):
    society, admin, manager, _ = _rig(db, "rx1")
    L = _ledgers(client, admin, society.id)
    r = _make(client, admin, society.id, L)
    assert r["name"] == "Security agency" and r["amount"] == "30000.00" and r["due_months"] == 1
    assert r["expense_account_name"] == "Security Charges" and r["element_name"]
    due = _due(client, admin, society.id)
    assert [(d["name"], d["month"], d["amount"]) for d in due] == [("Security agency", str(_month(0)), "30000.00")]
    assert due[0]["element_name"] == r["element_name"]

    v = _record(client, admin, r["id"], _month(0))
    assert v.status_code == 201, v.text
    voucher = v.json()
    assert voucher["voucher_type"] == "payment" and voucher["amount"] == "30000.00"
    assert "Security agency" in voucher["narration"] and "Shield Security" in voucher["narration"]
    sides = {e["account_name"]: (e["debit"], e["credit"]) for e in voucher["entries"]}
    assert sides["Security Charges"][0] == "30000.00" and sides["Cash in Hand"][1] == "30000.00"
    assert _due(client, admin, society.id) == []
    # it counts towards the element's spend
    report = client.get(f"{A}/expenses-by-element/{society.id}", headers=admin).json()
    security = next(e for e in report["elements"] if "Security" in e["name"])
    assert security["total"] == "30000.00"


def test_a_varying_bill_needs_the_amount_each_month(client, db):
    society, admin, manager, _ = _rig(db, "rx2")
    L = _ledgers(client, admin, society.id)
    r = _make(client, admin, society.id, L, head="electricity", name="Electricity bill", amount=None)
    assert r["amount"] is None and _due(client, admin, society.id)[0]["amount"] is None
    assert _record(client, admin, r["id"], _month(0)).status_code == 422
    assert _record(client, admin, r["id"], _month(0), amount="0").status_code == 422
    ok = _record(client, admin, r["id"], _month(0), amount="8450.50", reference="BILL-77", note="Sept reading")
    assert ok.status_code == 201
    assert ok.json()["amount"] == "8450.50" and ok.json()["reference"] == "BILL-77"
    # a fixed one can still be recorded at a different amount that month
    fixed = _make(client, admin, society.id, L, name="Housekeeping agency", head="housekeeping", amount="9000")
    assert _record(client, admin, fixed["id"], _month(0), amount="9250").json()["amount"] == "9250.00"


def test_missed_months_come_up_oldest_first_and_each_is_settled_once(client, db):
    society, admin, manager, _ = _rig(db, "rx3")
    L = _ledgers(client, admin, society.id)
    r = _make(client, admin, society.id, L, start_month=str(_month(3)))
    months = [d["month"] for d in _due(client, admin, society.id)]
    assert months[:3] == [str(_month(3)), str(_month(2)), str(_month(1))]
    assert _due(client, admin, society.id)[0]["days_late"] > 60
    assert _record(client, admin, r["id"], _month(3), voucher_date=str(_month(3))).status_code == 201
    # the same month can't be recorded or skipped again
    assert _record(client, admin, r["id"], _month(3)).status_code == 409
    skip = client.post(f"{A}/recurring-expenses/{r['id']}/skip", headers=admin,
                       json={"month": str(_month(2)), "reason": "Agency paid in advance"})
    assert skip.status_code == 200
    assert client.post(f"{A}/recurring-expenses/{r['id']}/skip", headers=admin,
                       json={"month": str(_month(2))}).status_code == 409
    assert [d["month"] for d in _due(client, admin, society.id)][:1] == [str(_month(1))]
    # a skip posts nothing: only the one payment is in the books
    vouchers = client.get(f"{A}/vouchers/society/{society.id}?voucher_type=payment", headers=admin).json()
    assert len(vouchers) == 1


def test_a_cancelled_payment_makes_its_month_due_again(client, db):
    society, admin, manager, _ = _rig(db, "rx4")
    L = _ledgers(client, admin, society.id)
    r = _make(client, admin, society.id, L)
    first = _record(client, admin, r["id"], _month(0)).json()
    assert _due(client, admin, society.id) == []
    c = client.post(f"{A}/vouchers/{first['id']}/cancel", headers=admin, json={"reason": "Entered twice"})
    assert c.status_code == 200, c.text
    assert [d["month"] for d in _due(client, admin, society.id)] == [str(_month(0))]
    again = _record(client, admin, r["id"], _month(0))
    assert again.status_code == 201 and again.json()["id"] != first["id"]
    assert _due(client, admin, society.id) == []


def test_future_and_out_of_period_months_are_refused(client, db):
    society, admin, manager, _ = _rig(db, "rx5")
    L = _ledgers(client, admin, society.id)
    nxt = _make(client, admin, society.id, L, start_month=str(_month(-1)))       # begins next month
    assert _due(client, admin, society.id) == []
    assert _record(client, admin, nxt["id"], _month(-1)).status_code == 422       # not due yet
    ended = _make(client, admin, society.id, L, name="Old AMC", start_month=str(_month(4)), end_month=str(_month(2)))
    due = [d for d in _due(client, admin, society.id) if d["name"] == "Old AMC"]
    assert [d["month"] for d in due] == [str(_month(4)), str(_month(3)), str(_month(2))]      # stops at its last month
    assert _record(client, admin, ended["id"], _month(1)).status_code == 422
    assert _record(client, admin, ended["id"], _month(5)).status_code == 422
    # the payment can't be dated in the future
    r = _make(client, admin, society.id, L, name="Rent")
    assert _record(client, admin, r["id"], _month(0), voucher_date="2999-01-01").status_code == 422


def test_the_day_falls_due_only_once_it_has_come(client, db):
    society, admin, manager, _ = _rig(db, "rx6")
    L = _ledgers(client, admin, society.id)
    late_in_month = _make(client, admin, society.id, L, day_of_month=31)
    due = [d for d in _due(client, admin, society.id) if d["recurring_id"] == late_in_month["id"]]
    # day 31 is capped to the month's last day, so it is due only from then
    import calendar
    last = calendar.monthrange(TODAY.year, TODAY.month)[1]
    assert bool(due) == (TODAY.day >= last)


def test_paused_expenses_are_not_due_and_resume(client, db):
    society, admin, manager, _ = _rig(db, "rx7")
    L = _ledgers(client, admin, society.id)
    r = _make(client, admin, society.id, L)
    p = client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"is_active": False})
    assert p.status_code == 200 and p.json()["is_active"] is False
    assert _due(client, admin, society.id) == []
    assert client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"is_active": True}).status_code == 200
    assert len(_due(client, admin, society.id)) == 1


def test_edit_changes_what_is_sent_and_paid_from_is_used(client, db):
    society, admin, manager, _ = _rig(db, "rx8")
    L = _ledgers(client, admin, society.id)
    r = _make(client, admin, society.id, L)
    bank = next(a for a in L.values() if a.get("is_bank"))
    p = client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin,
                     json={"amount": "31500", "paid_from_id": bank["id"], "note": "Revised from April"})
    assert p.status_code == 200
    body = p.json()
    assert body["amount"] == "31500.00" and body["paid_from_name"] == bank["name"] and body["name"] == "Security agency"
    v = _record(client, admin, r["id"], _month(0)).json()
    credit = next(e for e in v["entries"] if e["credit"] != "0.00")
    assert credit["account_name"] == bank["name"] and credit["credit"] == "31500.00"
    # a null clears an optional field; the name can't be blanked
    assert client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"amount": None}).json()["amount"] is None
    blank = client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"name": "  "})
    assert blank.status_code == 422


def test_input_is_checked(client, db):
    society, admin, manager, _ = _rig(db, "rx9")
    L = _ledgers(client, admin, society.id)
    base = {"society_id": str(society.id), "name": "X", "expense_account_id": L["security_charges"]["id"],
            "start_month": str(_month(0))}
    post = lambda **o: client.post(f"{A}/recurring-expenses", headers=admin, json={**base, **o}).status_code
    assert post() == 201
    assert post(name="   ") == 422
    assert post(expense_account_id=L["cash"]["id"]) == 422                  # not an expense head
    assert post(paid_from_id=L["security_charges"]["id"]) == 422            # not cash or bank
    assert post(amount="-5") == 422
    assert post(day_of_month=0) == 422 and post(day_of_month=32) == 422
    assert post(end_month=str(_month(2))) == 422                            # ends before it starts
    assert post(expense_account_id="00000000-0000-0000-0000-000000000000") == 422


def test_each_society_has_its_own_and_residents_have_none(client, db):
    society, admin, manager, resident = _rig(db, "rx10")
    other = make_society(db, "Other Society rx10")
    mine = _member(db, "sa@rx10.test", "Society Admin", society)
    theirs = _member(db, "sb@rx10.test", "Society Admin", other)
    L = _ledgers(client, mine, society.id)
    r = _make(client, mine, society.id, L)
    # another society's admin can't see, change, record or skip it
    assert client.get(f"{A}/recurring-expenses/{society.id}", headers=theirs).status_code == 403
    assert client.get(f"{A}/recurring-expenses/{society.id}/due", headers=theirs).status_code == 403
    assert client.patch(f"{A}/recurring-expenses/{r['id']}", headers=theirs, json={"name": "Mine"}).status_code == 404
    assert _record(client, theirs, r["id"], _month(0)).status_code == 404
    assert client.post(f"{A}/recurring-expenses/{r['id']}/skip", headers=theirs,
                       json={"month": str(_month(0))}).status_code == 404
    # ... nor create one in it, or use its ledgers in their own
    body = {"society_id": str(society.id), "name": "Sneaky", "expense_account_id": L["security_charges"]["id"]}
    assert client.post(f"{A}/recurring-expenses", headers=theirs, json=body).status_code == 403
    own = client.post(f"{A}/recurring-expenses", headers=theirs,
                      json={"name": "Sneaky", "expense_account_id": L["security_charges"]["id"]})
    assert own.status_code == 422                                           # a ledger of the other society
    # residents have no access to the books
    assert client.get(f"{A}/recurring-expenses/{society.id}", headers=resident).status_code == 403
    assert client.post(f"{A}/recurring-expenses", headers=resident, json=body).status_code == 403
    # a manager keeps them
    mgr = _member(db, "mg@rx10.test", "Manager", society)
    assert client.get(f"{A}/recurring-expenses/{society.id}", headers=mgr).status_code == 200
