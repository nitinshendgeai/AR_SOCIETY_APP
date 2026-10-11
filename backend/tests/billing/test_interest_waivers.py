"""Interest waivers: the committee waives the interest on one flat's arrears, or charges a lower rate, for a stretch of
days. Arrears here are one ₹3,650 bill that fell due 30 days ago, so interest at 12% is ₹36.00 (3,650 × 12% × 30/365)."""
from datetime import date, timedelta

from tests.billing.test_maintenance_calculation import _charge, _cycle, _preview, _rig, _settings
from tests.conftest import make_user

API = "/api/v1/billing"
TODAY = date.today()


def _arrears(client, db, tag):
    society, flats, h = _rig(db, tag, areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="12")
    _charge(client, h, society.id, "Maintenance", "fixed", "3650")
    first = _cycle(client, h, society.id, due_offset=-30, name="Earlier")
    client.post(f"{API}/cycles/{first}/generate-bills", headers=h)
    client.post(f"{API}/cycles/{first}/issue-all", headers=h)
    admin = make_user(db, f"admin@calc{tag}.com", role="Society Admin")["headers"]
    return society, flats[0], h, admin


def _waive(client, h, society, flat, **body):
    body.setdefault("mode", "waive")
    body.setdefault("from_date", str(TODAY - timedelta(days=60)))
    body.setdefault("reason", "Paid late because of a bank error")
    return client.post(f"{API}/interest-waivers", json={
        "society_id": str(society.id), "flat_id": str(flat.id), **body}, headers=h)


def _interest(client, h, society, name="Current"):
    cycle = _cycle(client, h, society.id, name=name)
    flat = _preview(client, h, cycle)["flats"][0]
    lines = [l for l in flat["lines"] if l["description"].startswith("Interest on arrears")]
    return cycle, flat, (lines[0] if lines else None)


def test_no_waiver_means_normal_interest(client, db):
    society, flat, h, _admin = _arrears(client, db, "iw0")
    _cycle_id, _f, line = _interest(client, h, society)
    assert line["amount"] == "36.00" and "committee" not in line["description"]


def test_waiving_all_interest_leaves_the_dues_and_consumes_the_days(client, db):
    society, flat, h, admin = _arrears(client, db, "iw1")
    assert _waive(client, admin, society, flat).status_code == 201
    cycle, f, line = _interest(client, h, society)
    assert line is None
    assert f["previous_dues"] == "3650.00"
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    bills = client.get(f"{API}/cycles/{cycle}/bills", headers=h).json()
    assert bills[0]["total_amount"] == "3650.00"
    # Cancelling later doesn't bring back interest for days that were already billed as nil
    waiver = client.get(f"{API}/interest-waivers/society/{society.id}", headers=h).json()[0]
    assert client.post(f"{API}/interest-waivers/{waiver['id']}/cancel", json={"reason": "x"}, headers=admin).status_code == 200
    _c, _f, again = _interest(client, h, society, name="Next")
    assert again is None


def test_lower_rate_replaces_the_societys_rate(client, db):
    society, flat, h, admin = _arrears(client, db, "iw2")
    assert _waive(client, admin, society, flat, mode="rate", rate_pct="6").status_code == 201
    _c, _f, line = _interest(client, h, society)
    assert line["amount"] == "18.00"
    assert "adjusted as approved by the committee" in line["description"]


def test_a_waiver_for_part_of_the_period_only_covers_those_days(client, db):
    society, flat, h, admin = _arrears(client, db, "iw3")
    # The first ten of the thirty days
    r = _waive(client, admin, society, flat, from_date=str(TODAY - timedelta(days=30)),
               to_date=str(TODAY - timedelta(days=21)))
    assert r.status_code == 201
    _c, _f, line = _interest(client, h, society)
    assert line["amount"] == "24.00"           # 3,650 × 12% × 20/365


def test_the_newest_waiver_wins_where_they_overlap(client, db):
    society, flat, h, admin = _arrears(client, db, "iw4")
    assert _waive(client, admin, society, flat).status_code == 201           # no interest, open-ended
    assert _waive(client, admin, society, flat, mode="rate", rate_pct="6",
                  from_date=str(TODAY - timedelta(days=30)), to_date=str(TODAY - timedelta(days=21))).status_code == 201
    _c, _f, line = _interest(client, h, society)
    assert line["amount"] == "6.00"            # ten days at 6%, the other twenty waived


def test_cancelled_waiver_stops_applying(client, db):
    society, flat, h, admin = _arrears(client, db, "iw5")
    w = _waive(client, admin, society, flat).json()
    r = client.post(f"{API}/interest-waivers/{w['id']}/cancel", json={"reason": "Raised in error"}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["cancel_reason"] == "Raised in error"
    assert client.post(f"{API}/interest-waivers/{w['id']}/cancel", json={"reason": "again"}, headers=admin).status_code == 409
    _c, _f, line = _interest(client, h, society)
    assert line["amount"] == "36.00"
    active = client.get(f"{API}/interest-waivers/society/{society.id}?status=active", headers=h).json()
    assert active == []


def test_waivers_need_a_reason_and_sensible_dates(client, db):
    society, flat, h, admin = _arrears(client, db, "iw6")
    assert _waive(client, admin, society, flat, reason="  ").status_code == 422
    assert _waive(client, admin, society, flat, mode="rate").status_code == 422                       # no rate given
    assert _waive(client, admin, society, flat, mode="rate", rate_pct="30").status_code == 422        # above the ceiling
    assert _waive(client, admin, society, flat, mode="half").status_code == 422
    assert _waive(client, admin, society, flat, from_date=str(TODAY),
                  to_date=str(TODAY - timedelta(days=1))).status_code == 422


def test_only_the_committee_or_admin_can_waive_but_a_manager_can_see(client, db):
    society, flat, h, admin = _arrears(client, db, "iw7")
    assert _waive(client, h, society, flat).status_code == 403            # the manager
    resident = make_user(db, "res@calciw7.com", role="Resident")["headers"]
    assert _waive(client, resident, society, flat).status_code == 403
    w = _waive(client, admin, society, flat).json()
    assert client.post(f"{API}/interest-waivers/{w['id']}/cancel", json={"reason": "x"}, headers=h).status_code == 403
    assert client.get(f"{API}/interest-waivers/society/{society.id}", headers=h).status_code == 200
    assert client.get(f"{API}/interest-waivers/society/{society.id}", headers=resident).status_code == 403


def test_waiver_is_scoped_to_the_flats_society(client, db):
    society, flat, h, admin = _arrears(client, db, "iw8")
    other, other_flats, _oh = _rig(db, "iw8b", areas=(600,))[0:3]
    r = _waive(client, admin, other, flat)          # this flat isn't in `other`
    assert r.status_code == 422
