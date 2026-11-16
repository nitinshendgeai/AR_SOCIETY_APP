"""Depreciation: the calculation worked by hand, the category rules and an asset's own setting, the schedule with its
journal and the assets it leaves out, and who may change what. Nothing is posted to the books."""
from datetime import date
from decimal import Decimal

from app.modules.accounts.services.depreciation import effective_rate, work_out
from tests.conftest import make_society, make_user

A = "/api/v1/accounts/depreciation"
INV = "/api/v1/inventory"
D = Decimal


# ── The calculation ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_reducing_balance_by_the_year():
    yrs = work_out(100000, "wdv", D("15"), 0, date(2026, 4, 1), None, 2027)
    assert [(y["opening"], y["depreciation"], y["closing"]) for y in yrs] == [
        (D("100000.00"), D("15000.00"), D("85000.00")),            # 100000 x 15%
        (D("85000.00"), D("12750.00"), D("72250.00")),             # on what is left
    ]


def test_part_of_a_year_is_by_days_in_use():
    # 1 Oct 2026 to 31 Mar 2027 is 182 of 365 days: 100000 x 15% x 182/365 = 7479.45
    (y,) = work_out(100000, "wdv", D("15"), 0, date(2026, 10, 1), None, 2026)
    assert y["days"] == 182 and y["depreciation"] == D("7479.45")
    # stopped on 30 Sep: 183 days, then nothing in later years
    yrs = work_out(100000, "wdv", D("15"), 0, date(2026, 4, 1), date(2026, 9, 30), 2027)
    assert yrs[0]["days"] == 183 and yrs[0]["depreciation"] == D("7520.55")
    assert yrs[1]["days"] == 0 and yrs[1]["depreciation"] == D("0.00")


def test_straight_line_stops_at_the_residual_value():
    yrs = work_out(120000, "slm", D("10"), 6000, date(2026, 4, 1), None, 2036)       # 12,000 a year; 6,000 is kept
    assert yrs[0]["depreciation"] == D("12000.00") and yrs[8]["closing"] == D("12000.00")
    assert yrs[9]["depreciation"] == D("6000.00") and yrs[9]["closing"] == D("6000.00")
    assert yrs[10]["depreciation"] == D("0.00")                                         # never below the residual value


def test_straight_line_rate_comes_from_the_life_when_none_is_given():
    assert effective_rate("slm", 0, 5) == D(20) and effective_rate("slm", D("12.5"), 5) == D("12.5")
    assert effective_rate("wdv", 0, 5) == D(0)                                           # reducing balance needs a rate


# ── The setup and the schedule ───────────────────────────────────────────────────────────────────────────────────────

def _member(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who


def _asset(client, who, **over):
    r = client.post(f"{INV}/assets", headers=who["headers"], json={"name": "Asset", "asset_category": "pump", **over})
    assert r.status_code == 201, r.text
    return r.json()


def _rig(db, tag):
    society = make_society(db, f"Dep Society {tag}")
    return (society, _member(db, f"adm@dep{tag}.test", "Society Admin", society),
            _member(db, f"mgr@dep{tag}.test", "Manager", society))


def test_schedule_journal_and_the_assets_left_out(client, db):
    society, admin, manager = _rig(db, "1")
    sid, h = str(society.id), admin["headers"]
    _asset(client, admin, name="Terrace pump", asset_category="pump", purchase_date="2026-04-01", purchase_cost="100000")
    _asset(client, admin, name="Office chairs", asset_category="furniture", purchase_date="2026-10-01", purchase_cost="50000")
    _asset(client, admin, name="Mystery box", asset_category="other")                    # no cost, no date

    r = client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=manager["headers"])
    assert r.status_code == 200, r.text
    s = r.json()
    by = {x["name"]: x for x in s["rows"]}
    assert by["Terrace pump"]["depreciation"] == "15000.00" and by["Terrace pump"]["closing_wdv"] == "85000.00"
    assert by["Office chairs"]["depreciation"] == "2493.15" and by["Office chairs"]["additions"] == "50000.00"   # 10% x 182/365
    assert s["totals"]["depreciation"] == "17493.15" and s["totals"]["closing_wdv"] == "132506.85"
    assert s["journal"]["debit"] == {"ledger": "Depreciation", "amount": "17493.15"}
    assert {c["ledger"]: c["amount"] for c in s["journal"]["credits"]} == {
        "Plant & Machinery (Lift, Pumps, DG)": "15000.00", "Furniture & Fixtures": "2493.15"}
    assert [p["name"] for p in s["problems"]] == ["Mystery box"]                       # left out, and said so
    assert "No purchase cost" in s["problems"][0]["issues"]

    # The next year carries the book value forward
    nxt = client.get(f"{A}/schedule/{sid}", params={"fy": "2027-28"}, headers=h).json()
    pump = next(x for x in nxt["rows"] if x["name"] == "Terrace pump")
    assert pump["opening_wdv"] == "85000.00" and pump["depreciation"] == "12750.00"

    # An asset bought after the year is not in it
    before = client.get(f"{A}/schedule/{sid}", params={"fy": "2025-26"}, headers=h).json()
    assert before["rows"] == [] and before["totals"]["depreciation"] == "0.00"

    pdf = client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27", "format": "pdf"}, headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.get(f"{A}/schedule/{sid}", params={"fy": "2026-2027"}, headers=h).status_code == 422


def test_the_category_rule_and_an_assets_own_setting(client, db):
    society, admin, manager = _rig(db, "2")
    sid, h = str(society.id), admin["headers"]
    pump = _asset(client, admin, name="Pump", asset_category="pump", purchase_date="2026-04-01", purchase_cost="100000")

    rules = client.get(f"{A}/rules/{sid}", headers=manager["headers"]).json()
    rule = next(r for r in rules if r["asset_category"] == "pump")
    assert rule["method"] == "wdv" and rule["rate"] == "15.0000" and len(rules) == 19      # one for every kind of asset

    assert client.patch(f"{A}/rules/{rule['id']}", json={"rate": "20"}, headers=manager["headers"]).status_code == 403
    assert client.patch(f"{A}/rules/{rule['id']}", json={"rate": "20"}, headers=h).status_code == 200
    s = client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()
    assert s["rows"][0]["depreciation"] == "20000.00"

    # The asset's own setting wins: straight line at 10%, keeping 10,000
    r = client.put(f"{A}/assets/{pump['id']}", json={"method": "slm", "rate": "10", "salvage_value": "10000"}, headers=h)
    assert r.status_code == 200 and r.json()["method"] == "slm" and r.json()["own"]["rate"] == "10.0000"
    s = client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()
    assert s["rows"][0]["depreciation"] == "10000.00"
    # ...and null goes back to the category's rule
    client.put(f"{A}/assets/{pump['id']}", json={"method": None, "rate": None, "salvage_value": None}, headers=h)
    assert client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()["rows"][0]["depreciation"] == "20000.00"

    # Not depreciated at all, then sold part-way through the year
    client.put(f"{A}/assets/{pump['id']}", json={"depreciate": False}, headers=h)
    assert client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()["rows"] == []
    client.put(f"{A}/assets/{pump['id']}", json={"depreciate": True, "stop_on": "2026-09-30"}, headers=h)
    assert client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()["rows"][0]["days"] == 183


def test_bad_settings_are_refused(client, db):
    society, admin, _manager = _rig(db, "3")
    sid, h = str(society.id), admin["headers"]
    pump = _asset(client, admin, purchase_date="2026-04-01", purchase_cost="1000")
    rule = next(r for r in client.get(f"{A}/rules/{sid}", headers=h).json() if r["asset_category"] == "pump")
    assert client.patch(f"{A}/rules/{rule['id']}", json={"method": "magic"}, headers=h).status_code == 422
    assert client.patch(f"{A}/rules/{rule['id']}", json={"rate": "120"}, headers=h).status_code == 422
    assert client.patch(f"{A}/rules/{rule['id']}", json={"method": "slm", "rate": "0"}, headers=h).status_code == 422   # no rate, no life
    assert client.put(f"{A}/assets/{pump['id']}", json={"start_on": "2026-06-01", "stop_on": "2026-05-01"}, headers=h).status_code == 422
    assert client.put(f"{A}/assets/{pump['id']}", json={"method": "magic"}, headers=h).status_code == 422


def test_disposed_assets_without_a_stop_date_are_flagged_not_depreciated(client, db):
    society, admin, _manager = _rig(db, "4")
    sid, h = str(society.id), admin["headers"]
    a = _asset(client, admin, name="Old DG", asset_category="generator", purchase_date="2020-04-01", purchase_cost="200000")
    assert client.patch(f"{INV}/assets/{a['id']}", json={"status": "disposed"}, headers=h).status_code == 200
    s = client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()
    assert s["rows"] == [] and "Disposed or lost: set the date it stopped being used" in s["problems"][0]["issues"]
    client.put(f"{A}/assets/{a['id']}", json={"stop_on": "2024-03-31"}, headers=h)
    s = client.get(f"{A}/schedule/{sid}", params={"fy": "2026-27"}, headers=h).json()
    assert s["rows"] == [] and s["problems"] == []                                       # finished before this year


def test_other_societies_and_residents_are_kept_out(client, db):
    society, admin, _m = _rig(db, "5")
    other, other_admin, _om = _rig(db, "6")
    pump = _asset(client, admin, purchase_date="2026-04-01", purchase_cost="1000")
    assert client.get(f"{A}/schedule/{other.id}", headers=admin["headers"]).status_code == 403
    assert client.get(f"{A}/rules/{other.id}", headers=admin["headers"]).status_code == 403
    assert client.put(f"{A}/assets/{pump['id']}", json={"rate": "5"}, headers=other_admin["headers"]).status_code == 403
    resident = _member(db, "res@dep5.test", "Resident", society)
    assert client.get(f"{A}/schedule/{society.id}", headers=resident["headers"]).status_code == 403
