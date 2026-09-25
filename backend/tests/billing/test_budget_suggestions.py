"""Suggested charge-head amounts from vendor bills — grouping by vendor
category, annualising a partial year, converting to each basis's unit, and
reporting spend no charge head covers."""
from datetime import date
from tests.conftest import make_user, make_society, make_wing, make_flat
from app.modules.billing.services.budget_suggestions import months_back


def _rig(db, tag):
    society = make_society(db, f"Budget Society {tag}")
    wing = make_wing(db, society.id, "A")
    for number, area in (("101", 1000), ("102", 1000), ("201", 2000)):
        f = make_flat(db, wing.id, number)
        f.area_sqft = area
    db.commit()
    admin = make_user(db, f"admin@budget{tag}.com", role="Society Admin")
    manager = make_user(db, f"mgr@budget{tag}.com", role="Manager")
    resident = make_user(db, f"res@budget{tag}.com", role="Resident")
    return society, admin["headers"], manager["headers"], resident["headers"]


def _charge_from_element(client, h, society_id, code, **patch):
    elements = client.get(f"/api/v1/billing/elements/{society_id}", headers=h).json()
    element = next(e for e in elements if e["code"] == code)
    r = client.post("/api/v1/billing/charges",
                    json={"society_id": str(society_id), "element_id": element["id"]}, headers=h)
    assert r.status_code == 201, r.text
    charge = r.json()
    if patch:
        r = client.patch(f"/api/v1/billing/charges/{charge['id']}", json=patch, headers=h)
        assert r.status_code == 200, r.text
        charge = r.json()
    return charge


_invoice_no = iter(range(1, 10_000))


def _bill(client, h, society_id, category, total, on):
    v = client.post("/api/v1/vendors/", json={
        "society_id": str(society_id), "company_name": f"{category} vendor {next(_invoice_no)}",
        "mobile": "9876543210", "category": category,
    }, headers=h)
    assert v.status_code == 201, v.text
    r = client.post("/api/v1/vendors/invoices", json={
        "society_id": str(society_id), "vendor_id": v.json()["id"],
        "invoice_number": f"INV-{next(_invoice_no)}", "invoice_date": str(on),
        "amount": total, "gst_amount": "0", "total_amount": total,
    }, headers=h)
    assert r.status_code == 201, r.text


def _suggestions(client, h, society_id, **params):
    r = client.get(f"/api/v1/billing/charges/{society_id}/budget-suggestions", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_suggests_amounts_per_basis_from_recent_vendor_bills(client, db):
    society, admin, manager, _ = _rig(db, "s1")
    security = _charge_from_element(client, manager, society.id, "security", default_amount="1")  # annual budget, split equally
    housekeeping = _charge_from_element(client, manager, society.id, "housekeeping",
                                        basis="fixed", default_amount="1")  # ₹ per flat per month
    lift = _charge_from_element(client, manager, society.id, "lift_maintenance",
                                basis="per_sqft", default_amount="1")  # ₹ per sq ft per month

    today = date.today()
    three_months_ago = months_back(today, 3)            # window covers 3 months of bills
    _bill(client, admin, society.id, "security", "30000.00", today)
    _bill(client, admin, society.id, "cctv", "6000.00", three_months_ago)
    _bill(client, admin, society.id, "housekeeping", "9000.00", today)
    _bill(client, admin, society.id, "lift", "12000.00", today)
    _bill(client, admin, society.id, "plumbing", "5000.00", today)
    _bill(client, admin, society.id, "security", "99999.00", months_back(today, 14))  # outside the window

    body = _suggestions(client, manager, society.id)
    assert body["months_covered"] == 3
    assert body["flat_count"] == 3
    by_id = {s["charge_id"]: s for s in body["suggestions"]}

    # Security + CCTV: 36,000 over 3 months → 1,44,000 a year, billed as the annual budget.
    s = by_id[security["id"]]
    assert (s["spent"], s["annual_estimate"], s["suggested_amount"]) == ("36000.00", "144000.00", "144000.00")
    assert s["vendor_categories"] == ["security", "cctv"]

    # Housekeeping: 9,000 over 3 months → 36,000 a year ÷ 3 flats ÷ 12 = ₹1,000 per flat per month.
    assert by_id[housekeeping["id"]]["suggested_amount"] == "1000.00"

    # Lift: 12,000 over 3 months → 48,000 a year ÷ 4,000 sq ft ÷ 12 = ₹1 per sq ft per month.
    assert by_id[lift["id"]]["suggested_amount"] == "1.00"

    # Plumbing isn't billed through any of these heads.
    assert body["unlinked"] == [{"category": "plumbing", "spent": "5000.00"}]


def test_heads_without_bills_or_mapping_get_no_suggestion(client, db):
    society, admin, manager, _ = _rig(db, "s2")
    water = _charge_from_element(client, manager, society.id, "water_charges", default_amount="240000")
    _charge_from_element(client, manager, society.id, "sinking_fund")  # % of construction cost — never suggested

    body = _suggestions(client, manager, society.id)
    assert body["months_covered"] == 0
    assert [s["charge_id"] for s in body["suggestions"]] == [water["id"]]
    assert body["suggestions"][0]["suggested_amount"] is None
    assert body["suggestions"][0]["current_amount"] == "240000.00"


def test_spend_on_a_head_the_society_does_not_bill_is_reported_unlinked(client, db):
    society, admin, manager, _ = _rig(db, "s3")
    _bill(client, admin, society.id, "security", "12000.00", date.today())
    body = _suggestions(client, manager, society.id)
    assert body["suggestions"] == []
    assert body["unlinked"] == [{"category": "security", "spent": "12000.00"}]


def test_residents_cannot_read_suggestions(client, db):
    society, admin, manager, resident = _rig(db, "s4")
    r = client.get(f"/api/v1/billing/charges/{society.id}/budget-suggestions", headers=resident)
    assert r.status_code == 403


def test_months_back_starts_on_the_first_of_the_month():
    assert months_back(date(2026, 9, 25), 12) == date(2025, 10, 1)
    assert months_back(date(2026, 1, 31), 1) == date(2026, 1, 1)
    assert months_back(date(2026, 3, 5), 3) == date(2026, 1, 1)
