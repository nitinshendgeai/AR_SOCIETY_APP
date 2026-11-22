"""The bill estimate: next month's bill for every flat, element by element, and the what-if for changing an element."""
from datetime import date
from decimal import Decimal

from app.modules.billing.models.billing import BillingCycle, MaintenanceBill
from app.modules.billing.services.bill_estimate import month_bounds
from tests.billing.test_maintenance_calculation import _charge, _rig
from tests.conftest import make_user

URL = "/api/v1/billing/estimate"


def _setup(client, db, tag):
    society, flats, h = _rig(db, tag, areas=(600, 1200))
    _charge(client, h, society.id, "Service Charges", "fixed", 1000)          # 1,000 a flat
    _charge(client, h, society.id, "Water Charges", "per_sqft", 2)             # 2 a sq ft
    return society, flats, h


def _estimate(client, h, society, **body):
    r = client.post(URL, json={"society_id": str(society.id), "month": "2030-06", **body}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _flat(est, label_end):
    return next(f for f in est["flats"] if f["flat_label"].endswith(label_end))


def _el(est, name):
    return next(e for e in est["elements"] if e["element"] == name)


def test_the_estimate_gives_every_flat_its_bill_element_by_element_and_the_rate_per_sq_ft(client, db):
    society, flats, h = _setup(client, db, "be1")
    est = _estimate(client, h, society)
    assert est["month"] == "2030-06" and est["month_label"] == "June 2030" and est["adjusted"] is False
    small, large = _flat(est, "101"), _flat(est, "201")
    assert {l["element"]: l["estimate"] for l in small["lines"]} == {"Service Charges": "1000.00",
                                                                     "Water Charges": "1200.00"}
    assert {l["element"]: l["estimate"] for l in large["lines"]} == {"Service Charges": "1000.00",
                                                                     "Water Charges": "2400.00"}
    assert (small["estimate_total"], large["estimate_total"]) == ("2200.00", "3400.00")
    assert small["area_sqft"] == 600 and small["estimate_per_sqft"] == "3.67"          # 2,200 / 600
    assert large["estimate_per_sqft"] == "2.83"                                         # 3,400 / 1,200
    assert est["totals"]["estimate"] == "5600.00" and est["totals"]["estimate_per_sqft"] == "3.11"   # 5,600 / 1,800
    assert est["totals"]["change"] == "0.00" and est["total_area_sqft"] == 1800
    assert _el(est, "Water Charges")["estimate_total"] == "3600.00"
    assert _el(est, "Water Charges")["estimate_per_sqft"] == "2.00"
    assert [e["element"] for e in est["elements"]] == ["Water Charges", "Service Charges"]       # largest first


def test_raising_an_element_by_a_percentage_shows_the_new_bills_and_rate(client, db):
    society, flats, h = _setup(client, db, "be2")
    est = _estimate(client, h, society, adjustments=[{"element": "Service Charges", "percent": "10"}])
    assert est["adjusted"] is True
    assert (_flat(est, "101")["estimate_total"], _flat(est, "201")["estimate_total"]) == ("2300.00", "3500.00")
    assert (_flat(est, "101")["current_total"], _flat(est, "101")["change"]) == ("2200.00", "100.00")
    service = _el(est, "Service Charges")
    assert (service["current_total"], service["estimate_total"], service["change"]) == ("2000.00", "2200.00", "200.00")
    assert service["change_pct"] == "10.00" and service["adjusted"] is True and _el(est, "Water Charges")["adjusted"] is False
    assert est["totals"]["current"] == "5600.00" and est["totals"]["estimate"] == "5800.00"
    assert est["totals"]["change"] == "200.00" and est["totals"]["estimate_per_sqft"] == "3.22"      # 5,800 / 1,800
    assert est["totals"]["current_per_sqft"] == "3.11"
    lower = _estimate(client, h, society, adjustments=[{"element": "Water Charges", "percent": "-50"}])
    assert lower["totals"]["estimate"] == "3800.00"                                                  # 2,000 + 1,800


def test_an_element_can_be_set_to_the_monthly_total_wanted_from_it(client, db):
    society, flats, h = _setup(client, db, "be3")
    est = _estimate(client, h, society, adjustments=[{"element": "Water Charges", "target_total": "4800"}])
    assert _el(est, "Water Charges")["estimate_total"] == "4800.00"
    assert (_flat(est, "101")["estimate_total"], _flat(est, "201")["estimate_total"]) == ("2600.00", "4200.00")
    assert est["totals"]["estimate"] == "6800.00"
    two = _estimate(client, h, society, adjustments=[{"element": "Water Charges", "percent": "0"},
                                                     {"element": "Service Charges", "target_total": "3000"}])
    assert _el(two, "Service Charges")["estimate_total"] == "3000.00" and two["totals"]["estimate"] == "6600.00"


def test_an_estimate_writes_nothing_and_asks_for_valid_figures(client, db):
    society, flats, h = _setup(client, db, "be4")
    _estimate(client, h, society, adjustments=[{"element": "Service Charges", "percent": "25"}])
    db.expire_all()
    assert db.query(BillingCycle).filter_by(society_id=society.id).count() == 0
    assert db.query(MaintenanceBill).filter_by(society_id=society.id).count() == 0
    heads = {c["name"]: c["default_amount"] for c in client.get(f"/api/v1/billing/charges/{society.id}", headers=h).json()}
    assert Decimal(heads["Service Charges"]) == Decimal("1000")                                     # the rate is unchanged
    both = client.post(URL, json={"society_id": str(society.id), "adjustments": [
        {"element": "Service Charges", "percent": "5", "target_total": "2000"}]}, headers=h)
    assert both.status_code == 422
    neither = client.post(URL, json={"society_id": str(society.id), "adjustments": [{"element": "Service Charges"}]},
                          headers=h)
    assert neither.status_code == 422
    unknown = client.post(URL, json={"society_id": str(society.id), "month": "2030-06", "adjustments": [
        {"element": "Nothing Like This", "target_total": "100"}]}, headers=h)
    assert unknown.status_code == 422
    assert client.post(URL, json={"society_id": str(society.id), "month": "2030-13"}, headers=h).status_code == 422
    below = client.post(URL, json={"society_id": str(society.id), "adjustments": [
        {"element": "Service Charges", "percent": "-101"}]}, headers=h)
    assert below.status_code == 422


def test_the_month_defaults_to_the_next_and_the_estimate_is_for_managers_of_the_society(client, db):
    assert month_bounds(None, date(2026, 11, 22)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert month_bounds(None, date(2026, 12, 5)) == (date(2027, 1, 1), date(2027, 1, 31))
    assert month_bounds("2028-02", date(2026, 1, 1)) == (date(2028, 2, 1), date(2028, 2, 29))
    society, flats, h = _setup(client, db, "be5")
    r = client.post(URL, json={"society_id": str(society.id)}, headers=h)
    assert r.status_code == 200 and r.json()["flats_count"] == 2
    resident = make_user(db, "res@be5.com", role="Resident")
    assert client.post(URL, json={"society_id": str(society.id)}, headers=resident["headers"]).status_code == 403
    outsider = make_user(db, "mgr@other-be5.com", role="Manager")
    from tests.conftest import make_society
    outsider["user"].society_id = make_society(db, "Other be5").id
    db.commit()
    assert client.post(URL, json={"society_id": str(society.id)}, headers=outsider["headers"]).status_code == 403


def test_an_element_can_be_billed_by_flat_area_keeping_the_societys_total(client, db):
    society, flats, h = _setup(client, db, "be6")          # Service Charges: 1,000 a flat = 2,000 for 600 + 1,200 sq ft
    est = _estimate(client, h, society, adjustments=[{"element": "Service Charges", "by_area": True}])
    small, large = _flat(est, "101"), _flat(est, "201")
    service = lambda f: next(l for l in f["lines"] if l["element"] == "Service Charges")
    assert (service(small)["current"], service(small)["estimate"]) == ("1000.00", "666.67")     # 600 x 2,000 / 1,800
    assert (service(large)["current"], service(large)["estimate"]) == ("1000.00", "1333.33")    # 1,200 x 2,000 / 1,800
    assert _el(est, "Service Charges")["estimate_total"] == "2000.00"                            # the society's total is kept
    assert _el(est, "Service Charges")["by_area"] is True and _el(est, "Water Charges")["by_area"] is False
    assert (small["estimate_total"], large["estimate_total"]) == ("1866.67", "3733.33")
    assert est["totals"]["estimate"] == "5600.00" and est["totals"]["current"] == "5600.00"
    assert est["adjusted"] is True


def test_by_area_can_follow_a_rise_or_a_new_total_and_a_rate_per_sq_ft_can_be_set(client, db):
    society, flats, h = _setup(client, db, "be7")
    rise = _estimate(client, h, society, adjustments=[{"element": "Service Charges", "percent": "10", "by_area": True}])
    assert _el(rise, "Service Charges")["estimate_total"] == "2200.00"                          # 2,000 + 10%, spread by area
    assert [next(l for l in _flat(rise, e)["lines"] if l["element"] == "Service Charges")["estimate"]
            for e in ("101", "201")] == ["733.33", "1466.67"]
    total = _estimate(client, h, society, adjustments=[{"element": "Service Charges", "target_total": "3600",
                                                        "by_area": True}])
    assert _el(total, "Service Charges")["estimate_total"] == "3600.00"                         # 2 a sq ft on 1,800 sq ft
    rate = _estimate(client, h, society, adjustments=[{"element": "Service Charges", "per_sqft": "3"}])
    assert [next(l for l in _flat(rate, e)["lines"] if l["element"] == "Service Charges")["estimate"]
            for e in ("101", "201")] == ["1800.00", "3600.00"]                                   # area x 3
    assert _el(rate, "Service Charges")["estimate_total"] == "5400.00"
    assert _el(rate, "Service Charges")["estimate_per_sqft"] == "3.00"
    assert (_flat(rate, "101")["estimate_total"], _flat(rate, "201")["estimate_total"]) == ("3000.00", "6000.00")


def test_by_area_needs_an_area_and_one_clear_change(client, db):
    society, flats, h = _setup(client, db, "be8")
    for f in flats:
        f.area_sqft = None
    db.commit()
    nobody = client.post(URL, json={"society_id": str(society.id), "month": "2030-06", "adjustments": [
        {"element": "Service Charges", "by_area": True}]}, headers=h)
    assert nobody.status_code == 422 and "area" in nobody.text
    rated = client.post(URL, json={"society_id": str(society.id), "month": "2030-06", "adjustments": [
        {"element": "Service Charges", "per_sqft": "3"}]}, headers=h)
    assert rated.status_code == 200
    assert any("no area recorded" in n for n in rated.json()["notes"])                           # they would pay nothing
    two = client.post(URL, json={"society_id": str(society.id), "adjustments": [
        {"element": "Service Charges", "per_sqft": "3", "percent": "5"}]}, headers=h)
    assert two.status_code == 422
    both = client.post(URL, json={"society_id": str(society.id), "adjustments": [
        {"element": "Service Charges", "per_sqft": "3", "by_area": True}]}, headers=h)
    assert both.status_code == 422
