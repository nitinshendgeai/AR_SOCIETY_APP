"""Spend per maintenance element: what the books show was spent on each element in a period, how an expense ledger
comes to count towards an element, and what is spent on ledgers that no element covers."""
from datetime import date
from app.utils.local_time import local_today, zone

from tests.billing.test_budget_suggestions import _rig
from tests.conftest import make_society, make_user

A = "/api/v1/accounts"
B = "/api/v1/billing"
TODAY = local_today(zone(None))


def _ledgers(client, h, sid):
    r = client.get(f"{A}/ledgers/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _pay(client, h, sid, ledgers, expense, amount, paid_from="cash", on=None, **extra):
    r = client.post(f"{A}/vouchers", headers=h, json={
        "society_id": str(sid), "voucher_type": "payment", "voucher_date": str(on or TODAY),
        "entries": [{"account_id": ledgers[expense]["id"], "debit": str(amount)},
                    {"account_id": ledgers[paid_from]["id"], "credit": str(amount)}], **extra})
    assert r.status_code == 201, r.text
    v = r.json()
    if v["approval_status"] == "pending":       # counts in the books (and in this report) only once approved
        ok = client.post(f"{A}/vouchers/{v['id']}/approve", json={}, headers=h)
        assert ok.status_code == 200, ok.text
    return v


def _report(client, h, sid, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"{A}/expenses-by-element/{sid}" + (f"?{q}" if q else ""), headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _by_name(report):
    return {e["name"]: e for e in report["elements"]}


def test_spend_adds_up_per_element_with_the_ledgers_behind_it(client, db):
    society, admin, manager, _ = _rig(db, "ee1")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "security_charges", 30000, "bank")
    _pay(client, admin, society.id, L, "cctv_maintenance", 1500)             # counts towards its own CCTV element
    _pay(client, admin, society.id, L, "electricity", 8450, "bank")
    r = _report(client, admin, society.id)
    els = _by_name(r)
    security = els["Security Services"]
    assert security["total"] == "30000.00"
    assert {l["name"]: l["amount"] for l in security["ledgers"]}["Security Charges"] == "30000.00"
    assert els["CCTV & Security Systems"]["total"] == "1500.00"
    assert len(els["Common Electricity"]["ledgers"]) >= 1
    electricity = next(e for n, e in els.items() if "Electricity" in n)
    assert electricity["total"] == "8450.00"
    assert r["linked_total"] == "39950.00" and r["unlinked_total"] == "0.00" and r["total"] == "39950.00"
    assert [e["total"] for e in r["elements"]][:2] == ["30000.00", "8450.00"]       # biggest first


def test_an_element_with_nothing_recorded_this_month_still_shows_at_zero(client, db):
    society, admin, manager, _ = _rig(db, "ee2")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "security_charges", 30000)
    els = _by_name(_report(client, admin, society.id))
    lift = next(e for n, e in els.items() if "Lift" in n)
    assert lift["total"] == "0.00"          # the cue that this month's lift bill hasn't been entered


def test_only_the_period_asked_for_counts(client, db):
    society, admin, manager, _ = _rig(db, "ee3")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "housekeeping", 9000, on="2026-08-10")
    _pay(client, admin, society.id, L, "housekeeping", 9500, on="2026-09-10")
    sep = _report(client, admin, society.id, date_from="2026-09-01", date_to="2026-09-30")
    assert next(e for e in sep["elements"] if e["total"] != "0.00")["total"] == "9500.00"
    both = _report(client, admin, society.id, date_from="2026-08-01", date_to="2026-09-30")
    assert both["total"] == "18500.00"
    assert client.get(f"{A}/expenses-by-element/{society.id}?date_from=2026-09-30&date_to=2026-09-01",
                      headers=admin).status_code == 422


def test_spend_on_a_ledger_no_element_covers_is_listed_apart_so_it_is_not_missed(client, db):
    society, admin, manager, _ = _rig(db, "ee4")
    L = _ledgers(client, admin, society.id)
    assert L["repairs_plumbing"]["maintenance_element_id"] is None
    _pay(client, admin, society.id, L, "repairs_plumbing", 2200)
    _pay(client, admin, society.id, L, "security_charges", 30000)
    r = _report(client, admin, society.id)
    assert [(u["name"], u["amount"]) for u in r["unlinked"]] == [(L["repairs_plumbing"]["name"], "2200.00")]
    assert r["unlinked_total"] == "2200.00" and r["linked_total"] == "30000.00" and r["total"] == "32200.00"


def test_linking_a_ledger_moves_its_spend_under_that_element(client, db):
    society, admin, manager, _ = _rig(db, "ee5")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "repairs_plumbing", 2200)
    water = next(e for e in client.get(f"{B}/elements/{society.id}", headers=manager).json() if e["code"] == "water_charges")
    assert client.patch(f"{A}/ledgers/{L['repairs_plumbing']['id']}", json={"maintenance_element_id": water["id"]},
                        headers=admin).status_code == 200
    r = _report(client, admin, society.id)
    assert r["unlinked"] == [] and _by_name(r)[water["name"]]["total"] == "2200.00"


def test_a_cancelled_voucher_and_a_refund_do_not_count_as_spend(client, db):
    society, admin, manager, _ = _rig(db, "ee6")
    L = _ledgers(client, admin, society.id)
    wrong = _pay(client, admin, society.id, L, "security_charges", 99999)
    assert client.post(f"{A}/vouchers/{wrong['id']}/cancel", json={"reason": "Entered twice"}, headers=admin).status_code == 200
    _pay(client, admin, society.id, L, "security_charges", 30000)
    refund = client.post(f"{A}/vouchers", headers=admin, json={
        "society_id": str(society.id), "voucher_type": "receipt", "voucher_date": str(TODAY),
        "entries": [{"account_id": L["cash"]["id"], "debit": "1000"},
                    {"account_id": L["security_charges"]["id"], "credit": "1000"}]})
    assert refund.status_code == 201, refund.text
    r = _report(client, admin, society.id)
    assert next(e for e in r["elements"] if "Security" in e["name"])["total"] == "29000.00"


def test_only_the_societys_own_books_staff_can_read_it(client, db):
    society, admin, manager, _ = _rig(db, "ee7")
    other = make_society(db, "Other Books Society")
    outsider = make_user(db, "ee7-out@test.com", role="Society Admin")
    outsider["user"].society_id = other.id
    db.commit()
    resident = make_user(db, "ee7-res@test.com", role="Resident")
    resident["user"].society_id = society.id
    db.commit()
    assert client.get(f"{A}/expenses-by-element/{society.id}", headers=outsider["headers"]).status_code == 403
    assert client.get(f"{A}/expenses-by-element/{society.id}", headers=resident["headers"]).status_code == 403
    assert client.get(f"{A}/expenses-by-element/{society.id}", headers=manager).status_code == 200


def _months(client, h, sid, element_id, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"{A}/expenses-by-element/{sid}/months?element_id={element_id}" + (f"&{q}" if q else ""), headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_an_element_shows_month_by_month_with_the_ledgers_behind_each_month(client, db):
    society, admin, manager, _ = _rig(db, "ee8")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "security_charges", 30000, on="2026-08-10")
    _pay(client, admin, society.id, L, "security_charges", 31000, on="2026-10-05")
    _pay(client, admin, society.id, L, "cctv_maintenance", 1500, on="2026-10-20")          # another element
    _pay(client, admin, society.id, L, "housekeeping", 9000, on="2026-09-10")             # another element
    report = _report(client, admin, society.id, date_from="2026-08-01", date_to="2026-10-31")
    security = _by_name(report)["Security Services"]
    m = _months(client, admin, society.id, security["element_id"], date_from="2026-08-01", date_to="2026-10-31")
    assert m["title"] == "Security Services" and m["total"] == "61000.00"
    assert [(x["month"], x["label"], x["total"]) for x in m["months"]] == [
        ("2026-08", "Aug 2026", "30000.00"), ("2026-09", "Sep 2026", "0.00"), ("2026-10", "Oct 2026", "31000.00")]
    assert m["months"][0]["ledgers"] == [{"account_id": L["security_charges"]["id"], "name": "Security Charges",
                                          "amount": "30000.00"}]
    assert m["months"][1]["ledgers"] == []                                                   # an empty month is listed
    assert m["total"] == security["total"]                                                    # the same figure as the report


def test_the_months_follow_the_dates_asked_for_and_leave_out_cancelled_and_refunded_spend(client, db):
    society, admin, manager, _ = _rig(db, "ee9")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "security_charges", 30000, on="2026-08-31")        # the last day of a month
    _pay(client, admin, society.id, L, "security_charges", 31000, on="2026-09-01")        # the first of the next
    wrong = _pay(client, admin, society.id, L, "security_charges", 999, on="2026-09-15")
    assert client.post(f"{A}/vouchers/{wrong['id']}/cancel", json={"reason": "Entered twice"}, headers=admin).status_code == 200
    refund = client.post(f"{A}/vouchers", headers=admin, json={
        "society_id": str(society.id), "voucher_type": "receipt", "voucher_date": "2026-09-20",
        "entries": [{"account_id": L["cash"]["id"], "debit": "1000"},
                    {"account_id": L["security_charges"]["id"], "credit": "1000"}]})
    assert refund.status_code == 201, refund.text
    if refund.json()["approval_status"] == "pending":
        assert client.post(f"{A}/vouchers/{refund.json()['id']}/approve", json={}, headers=admin).status_code == 200
    eid = _by_name(_report(client, admin, society.id))["Security Services"]["element_id"]
    both = _months(client, admin, society.id, eid, date_from="2026-08-01", date_to="2026-09-30")
    assert [(x["month"], x["total"]) for x in both["months"]] == [("2026-08", "30000.00"), ("2026-09", "30000.00")]
    sep = _months(client, admin, society.id, eid, date_from="2026-09-01", date_to="2026-09-30")
    assert [(x["month"], x["total"]) for x in sep["months"]] == [("2026-09", "30000.00")]      # 31,000 - 1,000 refund
    aug = _months(client, admin, society.id, eid, date_from="2026-08-15", date_to="2026-08-31")
    assert aug["total"] == "30000.00" and len(aug["months"]) == 1                              # a part month still counts
    assert _months(client, admin, society.id, eid, date_from="2026-06-01", date_to="2026-07-31")["total"] == "0.00"


def test_spend_no_element_covers_has_its_own_month_view_and_bad_requests_are_refused(client, db):
    society, admin, manager, _ = _rig(db, "ee10")
    L = _ledgers(client, admin, society.id)
    _pay(client, admin, society.id, L, "repairs_plumbing", 700, on="2026-09-03")           # linked to no element
    none = _months(client, admin, society.id, "none", date_from="2026-09-01", date_to="2026-09-30")
    assert none["title"] == "Not counted towards any element" and none["total"] == "700.00"
    assert [l["amount"] for l in none["months"][0]["ledgers"]] == ["700.00"]               # the ledger behind the month
    base = f"{A}/expenses-by-element/{society.id}/months"
    assert client.get(f"{base}?element_id=none&date_from=2026-09-30&date_to=2026-09-01", headers=admin).status_code == 422
    assert client.get(f"{base}?element_id=none&date_from=2020-01-01&date_to=2026-09-01", headers=admin).status_code == 422
    assert client.get(f"{base}?element_id=not-an-id", headers=admin).status_code == 422
    assert client.get(f"{base}?element_id=00000000-0000-0000-0000-000000000000", headers=admin).status_code == 404
    other = make_society(db, "Other Months Society")
    outsider = make_user(db, "ee10-out@test.com", role="Society Admin")
    outsider["user"].society_id = other.id
    db.commit()
    assert client.get(f"{base}?element_id=none", headers=outsider["headers"]).status_code == 403
    assert client.get(f"{base}?element_id=none", headers=manager).status_code == 200
