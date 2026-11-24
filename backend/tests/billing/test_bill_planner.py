"""The budget planner: the monthly cost of each element and common area, shared over the flats by area or equally."""
from decimal import Decimal

from tests.billing.test_maintenance_calculation import _charge, _rig
from tests.conftest import make_society, make_user

URL = "/api/v1/billing/estimate/plan"


def _plan(client, h, society, lines, **body):
    r = client.post(URL, json={"society_id": str(society.id), "month": "2030-06", "lines": lines, **body}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _flat(plan, end):
    return next(f for f in plan["flats"] if f["flat_label"].endswith(end))


def test_the_plan_totals_the_lines_and_gives_the_rate_per_sq_ft_and_each_flats_share(client, db):
    society, flats, h = _rig(db, "pl1", areas=(600, 1200))             # 1,800 sq ft in all
    plan = _plan(client, h, society, [{"name": "Security", "amount": "90000", "split": "area"},
                                      {"name": "Gym", "amount": "9000"}])               # a line is by area unless said
    assert plan["total"] == "99000.00" and plan["area_total_sqft"] == 1800 and plan["flats_count"] == 2
    assert plan["rate_per_sqft"] == "55.00" and plan["average_per_sqft"] == "55.00"      # 99,000 / 1,800
    assert [(l["name"], l["rate_per_sqft"]) for l in plan["lines"]] == [("Security", "50.0000"), ("Gym", "5.0000")]
    small, large = _flat(plan, "101"), _flat(plan, "201")
    assert {s["name"]: s["amount"] for s in small["shares"]} == {"Security": "30000.00", "Gym": "3000.00"}   # 600 x 50, 600 x 5
    assert {s["name"]: s["amount"] for s in large["shares"]} == {"Security": "60000.00", "Gym": "6000.00"}
    assert (small["total"], large["total"]) == ("33000.00", "66000.00")
    assert small["per_sqft"] == "55.00" and large["per_sqft"] == "55.00"                  # the same rate for every flat
    assert plan["collected"] == "99000.00"


def test_a_line_can_be_shared_equally_and_mixed_with_area_lines(client, db):
    society, flats, h = _rig(db, "pl2", areas=(600, 1200))
    plan = _plan(client, h, society, [{"name": "Office", "amount": "3000", "split": "equal"},
                                      {"name": "Podium", "amount": "1800", "split": "area"}])
    assert plan["per_flat_equal"] == "1500.00" and plan["rate_per_sqft"] == "1.00"
    assert [l["per_flat"] for l in plan["lines"]] == ["1500.00", None]
    small, large = _flat(plan, "101"), _flat(plan, "201")
    assert (small["total"], large["total"]) == ("2100.00", "2700.00")                    # 1,500 + 600, 1,500 + 1,200
    assert small["per_sqft"] == "3.50" and large["per_sqft"] == "2.25"                    # the small flat pays more a sq ft
    assert plan["average_per_sqft"] == "2.67"                                              # 4,800 / 1,800
    zero = _plan(client, h, society, [{"name": "Nothing yet", "amount": "0"}])
    assert zero["total"] == "0.00" and _flat(zero, "101")["total"] == "0.00"


def test_the_plan_sits_beside_what_the_charge_heads_bill_now(client, db):
    society, flats, h = _rig(db, "pl3", areas=(600, 1200))
    _charge(client, h, society.id, "Service Charges", "fixed", 1000)                      # 1,000 a flat now
    plan = _plan(client, h, society, [{"name": "Everything", "amount": "3600"}])           # 2 a sq ft
    small, large = _flat(plan, "101"), _flat(plan, "201")
    assert (small["current"], small["total"], small["change"]) == ("1000.00", "1200.00", "200.00")
    assert (large["current"], large["total"], large["change"]) == ("1000.00", "2400.00", "1400.00")
    assert plan["compared"] is True and plan["totals"] == {"current": "2000.00", "change": "1600.00"}
    assert plan["month_label"] == "June 2030"
    bare = _plan(client, h, society, [{"name": "Everything", "amount": "3600"}], compare=False)
    assert bare["compared"] is False and bare["totals"] is None and "current" not in bare["flats"][0]


def test_flats_without_an_area_are_named_and_bad_requests_are_refused(client, db):
    society, flats, h = _rig(db, "pl4", areas=(600, 1200))
    flats[0].area_sqft = None
    db.commit()
    plan = _plan(client, h, society, [{"name": "Gym", "amount": "1200"}], compare=False)
    assert _flat(plan, "101")["total"] == "0.00" and _flat(plan, "201")["total"] == "1200.00"     # the whole sum falls on 1,200 sq ft
    assert any("no area recorded" in n for n in plan["notes"])
    flats[1].area_sqft = None
    db.commit()
    assert client.post(URL, json={"society_id": str(society.id), "lines": [{"name": "Gym", "amount": "5"}]},
                       headers=h).status_code == 422                                          # nothing to share by area
    equal = client.post(URL, json={"society_id": str(society.id), "compare": False,
                                   "lines": [{"name": "Office", "amount": "100", "split": "equal"}]}, headers=h)
    assert equal.status_code == 200 and equal.json()["per_flat_equal"] == "50.00"             # equal needs no area
    for bad in ([], [{"name": "", "amount": "5"}], [{"name": "X", "amount": "-1"}],
                [{"name": "X", "amount": "5", "split": "random"}]):
        assert client.post(URL, json={"society_id": str(society.id), "lines": bad}, headers=h).status_code == 422
    assert client.post(URL, json={"society_id": str(society.id), "month": "2030-13",
                                  "lines": [{"name": "X", "amount": "5"}]}, headers=h).status_code == 422


def test_the_planner_is_for_managers_of_the_society_and_writes_nothing(client, db):
    society, flats, h = _rig(db, "pl5", areas=(600, 1200))
    line = [{"name": "Gym", "amount": "1200"}]
    resident = make_user(db, "res@pl5.com", role="Resident")
    assert client.post(URL, json={"society_id": str(society.id), "lines": line}, headers=resident["headers"]).status_code == 403
    outsider = make_user(db, "mgr@other-pl5.com", role="Manager")
    outsider["user"].society_id = make_society(db, "Other pl5").id
    db.commit()
    assert client.post(URL, json={"society_id": str(society.id), "lines": line}, headers=outsider["headers"]).status_code == 403
    _plan(client, h, society, line)
    heads = client.get(f"/api/v1/billing/charges/{society.id}", headers=h).json()
    assert heads == []                                                                       # no charge head was made


def test_amounts_can_be_per_month_quarter_or_year_and_the_plan_reports_all_three(client, db):
    society, flats, h = _rig(db, "pl6", areas=(600, 1200))                              # 1,800 sq ft
    plan = _plan(client, h, society, [{"name": "Insurance", "amount": "36000", "period": "year"},     # 3,000 a month
                                      {"name": "Security", "amount": "9000", "period": "month"}])
    insurance = plan["lines"][0]
    assert (insurance["amount"], insurance["period"]) == ("36000.00", "year")             # as typed
    assert insurance["by_period"] == {"monthly": "3000.00", "quarterly": "9000.00", "yearly": "36000.00"}
    assert plan["lines"][1]["by_period"] == {"monthly": "9000.00", "quarterly": "27000.00", "yearly": "108000.00"}
    p = plan["periods"]
    assert [p[k]["total"] for k in ("monthly", "quarterly", "yearly")] == ["12000.00", "36000.00", "144000.00"]
    assert [p[k]["rate_per_sqft"] for k in ("monthly", "quarterly", "yearly")] == ["6.67", "20.00", "80.00"]
    assert [p[k]["shortfall"] for k in ("monthly", "quarterly", "yearly")] == ["0.00"] * 3
    assert plan["total"] == "12000.00" and plan["rate_per_sqft"] == "6.67"                 # the monthly fields are unchanged
    small, large = _flat(plan, "101"), _flat(plan, "201")
    assert [small["by_period"][k]["total"] for k in ("monthly", "quarterly", "yearly")] == ["4000.00", "12000.00", "48000.00"]
    assert [large["by_period"][k]["total"] for k in ("monthly", "quarterly", "yearly")] == ["8000.00", "24000.00", "96000.00"]
    assert small["by_period"]["quarterly"]["per_sqft"] == "20.00" and small["by_period"]["yearly"]["per_sqft"] == "80.00"
    quarter = {s["name"]: s["amount"] for s in small["by_period"]["quarterly"]["shares"]}
    assert quarter == {"Insurance": "3000.00", "Security": "9000.00"}                       # 600 / 1,800 of 9,000 and 27,000
    assert plan["lines"][0]["rate_by_period"] == {"monthly": "1.6667", "quarterly": "5.0000", "yearly": "20.0000"}


def test_a_typed_total_area_sets_the_rate_and_the_shortfall_is_shown(client, db):
    society, flats, h = _rig(db, "pl7", areas=(600, 1200))                              # the flats add up to 1,800 sq ft
    plan = _plan(client, h, society, [{"name": "Gym", "amount": "9000"}], total_area_sqft="2000", compare=False)
    assert plan["area_source"] == "typed" and plan["area_total_sqft"] == 2000 and plan["flats_area_sqft"] == 1800
    assert plan["rate_per_sqft"] == "4.50"                                                  # 9,000 / 2,000
    assert (_flat(plan, "101")["total"], _flat(plan, "201")["total"]) == ("2700.00", "5400.00")
    assert plan["periods"]["monthly"]["collected"] == "8100.00" and plan["periods"]["monthly"]["shortfall"] == "900.00"
    assert plan["periods"]["yearly"]["shortfall"] == "10800.00"
    assert any("You typed a total area of 2,000 sq ft" in n for n in plan["notes"])
    same = _plan(client, h, society, [{"name": "Gym", "amount": "9000"}], total_area_sqft="1800", compare=False)
    assert same["area_source"] == "typed" and same["periods"]["monthly"]["shortfall"] == "0.00"
    assert not any("You typed" in n for n in same["notes"])                                 # nothing to point out
    default = _plan(client, h, society, [{"name": "Gym", "amount": "9000"}], compare=False)
    assert default["area_source"] == "flats" and default["area_total_sqft"] == 1800
    for bad in ("0", "-5"):
        r = client.post(URL, json={"society_id": str(society.id), "total_area_sqft": bad,
                                   "lines": [{"name": "Gym", "amount": "5"}]}, headers=h)
        assert r.status_code == 422


def test_the_comparison_follows_the_period_and_a_typed_area_needs_no_flat_areas(client, db):
    society, flats, h = _rig(db, "pl8", areas=(600, 1200))
    _charge(client, h, society.id, "Service Charges", "fixed", 1000)                      # 1,000 a flat a month now
    plan = _plan(client, h, society, [{"name": "Everything", "amount": "3600"}])
    small = _flat(plan, "101")["by_period"]
    assert (small["monthly"]["current"], small["monthly"]["total"], small["monthly"]["change"]) == ("1000.00", "1200.00", "200.00")
    assert (small["quarterly"]["current"], small["quarterly"]["total"], small["quarterly"]["change"]) == ("3000.00", "3600.00", "600.00")
    assert (small["yearly"]["current"], small["yearly"]["total"], small["yearly"]["change"]) == ("12000.00", "14400.00", "2400.00")
    for f in flats:
        f.area_sqft = None
    db.commit()
    typed = _plan(client, h, society, [{"name": "Gym", "amount": "1200"}], total_area_sqft="1200", compare=False)
    assert typed["rate_per_sqft"] == "1.00" and typed["area_source"] == "typed"            # no flat has an area: the typed one is used
    assert _flat(typed, "101")["total"] == "0.00"                                           # but a flat with no area pays nothing
