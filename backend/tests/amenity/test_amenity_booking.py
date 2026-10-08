"""Amenity booking: hours and capacity, the rules, clashes, approval, who may do what, keeping societies apart,
the day view, prices and rate rules."""
from datetime import date, time, timedelta

import pytest

from tests.conftest import make_flat, make_society, make_user

A = "/api/v1/amenities"


def _ahead(days):
    return str(date.today() + timedelta(days=days))


def make_wing(db, society_id, name):
    from app.models.wing import Wing
    w = Wing(society_id=society_id, name=name, code=name)
    db.add(w); db.commit(); db.refresh(w)
    return w


def _member(db, email, role, society, name=None):
    who = make_user(db, email, role=role, full_name=name or email.split("@")[0])
    who["user"].society_id = society.id
    db.commit()
    return who


@pytest.fixture
def soc(db):
    society = make_society(db, "Amenity Booking Society")
    wing = make_wing(db, society.id, "A")
    flat = make_flat(db, wing.id, "101")
    r = {
        "society": society, "flat": flat,
        "admin": _member(db, "admin@ab.test", "Society Admin", society, "Asha Admin"),
        "res": _member(db, "res@ab.test", "Resident", society, "Rohan Resident"),
        "res2": _member(db, "res2@ab.test", "Resident", society, "Ravi Resident"),
        "guard": _member(db, "guard@ab.test", "Security Staff", society, "Gopal Guard"),
    }
    from app.models.resident import Resident, ResidentType
    db.add(Resident(flat_id=flat.id, user_id=r["res"]["user"].id, full_name="Rohan Resident", phone="9000000010",
                    resident_type=ResidentType.OWNER, is_active=True))
    db.commit()
    return r


def _amenity(client, soc, name="Clubhouse", **extra):
    body = {"name": name, "amenity_type": "clubhouse", "open_time": "06:00:00", "close_time": "22:00:00",
            "capacity": 40, **extra}
    r = client.post(f"{A}/", json=body, headers=soc["admin"]["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def _book(client, who, amenity_id, day=3, start="10:00:00", end="12:00:00", **extra):
    return client.post(f"{A}/bookings", json={"amenity_id": amenity_id, "booking_date": _ahead(day),
                                              "start_time": start, "end_time": end, **extra}, headers=who["headers"])


def _rule(client, soc, amenity_id, rule_type, value=None):
    return client.post(f"{A}/{amenity_id}/rules", json={"rule_type": rule_type, "rule_value": value},
                       headers=soc["admin"]["headers"])


# ── Setting up ────────────────────────────────────────────────────────────────

def test_society_comes_from_the_login_and_a_name_is_unique(client, soc):
    a = _amenity(client, soc)
    assert a["society_id"] == str(soc["society"].id)
    dup = client.post(f"{A}/", json={"name": "clubhouse", "amenity_type": "clubhouse"}, headers=soc["admin"]["headers"])
    assert dup.status_code == 409


def test_it_must_close_after_it_opens(client, soc):
    r = client.post(f"{A}/", json={"name": "Odd", "amenity_type": "gym", "open_time": "20:00:00",
                                   "close_time": "08:00:00"}, headers=soc["admin"]["headers"])
    assert r.status_code == 422


def test_closing_an_amenity_hides_it_and_stops_booking(client, soc):
    a = _amenity(client, soc)
    assert client.patch(f"{A}/{a['id']}", json={"is_active": False}, headers=soc["admin"]["headers"]).status_code == 200
    listed = client.get(f"{A}/society/{soc['society'].id}", headers=soc["res"]["headers"]).json()
    assert a["id"] not in [x["id"] for x in listed]
    assert _book(client, soc["res"], a["id"]).status_code == 409


# ── Booking checks ────────────────────────────────────────────────────────────

def test_a_booking_inside_the_hours_is_made_and_gets_the_residents_flat(client, soc):
    a = _amenity(client, soc)
    r = _book(client, soc["res"], a["id"])
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "approved"
    assert b["flat"] == "A / 101"
    assert b["amenity_name"] == "Clubhouse"
    assert b["booked_by_name"] == "Rohan Resident"


def test_outside_opening_hours_is_refused(client, soc):
    a = _amenity(client, soc)
    r = _book(client, soc["res"], a["id"], start="04:00:00", end="05:00:00")
    assert r.status_code == 422
    assert "opens at 6:00 AM" in str(r.json())
    r = _book(client, soc["res"], a["id"], start="21:00:00", end="23:00:00")
    assert r.status_code == 422
    assert "closes at 10:00 PM" in str(r.json())


def test_more_people_than_capacity_is_refused(client, soc):
    a = _amenity(client, soc, capacity=10)
    assert _book(client, soc["res"], a["id"], guest_count=11).status_code == 422
    assert _book(client, soc["res"], a["id"], guest_count=10).status_code == 201


def test_a_time_already_begun_is_refused(client, soc):
    a = _amenity(client, soc, open_time=None, close_time=None)
    r = _book(client, soc["res"], a["id"], day=0, start="00:00:00", end="00:30:00")
    assert r.status_code == 422
    assert "already begun" in str(r.json())
    assert _book(client, soc["res"], a["id"], day=-2).status_code == 422


def test_overlap_is_refused_but_back_to_back_is_fine(client, soc):
    a = _amenity(client, soc)
    assert _book(client, soc["res"], a["id"], start="10:00:00", end="12:00:00").status_code == 201
    assert _book(client, soc["res2"], a["id"], start="11:00:00", end="13:00:00").status_code == 409
    assert _book(client, soc["res2"], a["id"], start="12:00:00", end="13:00:00").status_code == 201


def test_a_cancelled_booking_frees_the_time(client, soc):
    a = _amenity(client, soc)
    first = _book(client, soc["res"], a["id"]).json()
    assert client.post(f"{A}/bookings/{first['id']}/cancel", json={"reason": "Not needed"},
                       headers=soc["res"]["headers"]).status_code == 200
    assert _book(client, soc["res2"], a["id"]).status_code == 201


def test_a_closed_date_blocks_booking(client, soc):
    a = _amenity(client, soc)
    r = client.post(f"{A}/{a['id']}/blackouts", json={"blackout_date": _ahead(3), "reason": "Painting"},
                    headers=soc["admin"]["headers"])
    assert r.status_code == 201
    assert _book(client, soc["res"], a["id"], day=3).status_code == 409
    dup = client.post(f"{A}/{a['id']}/blackouts", json={"blackout_date": _ahead(3)}, headers=soc["admin"]["headers"])
    assert dup.status_code == 409
    past = client.post(f"{A}/{a['id']}/blackouts", json={"blackout_date": _ahead(-3)}, headers=soc["admin"]["headers"])
    assert past.status_code == 422


def test_an_amenity_that_needs_no_booking_cannot_be_booked(client, soc):
    a = _amenity(client, soc, name="Garden", booking_required=False)
    assert _book(client, soc["res"], a["id"]).status_code == 409


def test_a_flat_that_is_not_yours_is_refused(client, soc, db):
    other = make_flat(db, make_wing(db, soc["society"].id, "B").id, "201")
    a = _amenity(client, soc)
    r = _book(client, soc["res"], a["id"], flat_id=str(other.id))
    assert r.status_code == 422


# ── Rules ─────────────────────────────────────────────────────────────────────

def test_the_rules_are_enforced(client, soc):
    a = _amenity(client, soc)
    assert _rule(client, soc, a["id"], "max_duration_hours", "2").status_code == 201
    assert _rule(client, soc, a["id"], "max_guests", "5").status_code == 201
    assert _rule(client, soc, a["id"], "max_advance_days", "10").status_code == 201
    assert _book(client, soc["res"], a["id"], start="10:00:00", end="13:00:00").status_code == 422
    assert _book(client, soc["res"], a["id"], guest_count=6).status_code == 422
    assert _book(client, soc["res"], a["id"], day=20).status_code == 422
    assert _book(client, soc["res"], a["id"], start="10:00:00", end="12:00:00", guest_count=5).status_code == 201


def test_weekly_limit_counts_only_live_bookings(client, soc):
    a = _amenity(client, soc)
    _rule(client, soc, a["id"], "max_bookings_per_month", "1")
    first = _book(client, soc["res"], a["id"], day=3, start="08:00:00", end="09:00:00")
    assert first.status_code == 201
    assert _book(client, soc["res"], a["id"], day=3, start="10:00:00", end="11:00:00").status_code == 422
    client.post(f"{A}/bookings/{first.json()['id']}/cancel", json={}, headers=soc["res"]["headers"])
    assert _book(client, soc["res"], a["id"], day=3, start="10:00:00", end="11:00:00").status_code == 201


def test_setting_a_rule_again_replaces_it(client, soc):
    a = _amenity(client, soc)
    _rule(client, soc, a["id"], "max_guests", "5")
    _rule(client, soc, a["id"], "max_guests", "8")
    rules = client.get(f"{A}/{a['id']}/rules", headers=soc["res"]["headers"]).json()
    assert [r["rule_value"] for r in rules if r["rule_type"] == "max_guests"] == ["8"]


def test_a_rule_value_is_validated(client, soc):
    a = _amenity(client, soc)
    assert _rule(client, soc, a["id"], "max_guests", "lots").status_code == 422
    assert _rule(client, soc, a["id"], "max_guests", "0").status_code == 422
    assert _rule(client, soc, a["id"], "max_guests", "2.5").status_code == 422
    assert _rule(client, soc, a["id"], "max_duration_hours", "1.5").status_code == 201


def test_removing_a_rule_lifts_it(client, soc):
    a = _amenity(client, soc)
    rule = _rule(client, soc, a["id"], "max_guests", "2").json()
    assert _book(client, soc["res"], a["id"], guest_count=3).status_code == 422
    assert client.delete(f"{A}/rules/{rule['id']}", headers=soc["admin"]["headers"]).status_code == 204
    assert _book(client, soc["res"], a["id"], guest_count=3).status_code == 201


# ── Approval ──────────────────────────────────────────────────────────────────

def test_approval_flow_and_who_may_decide(client, soc):
    a = _amenity(client, soc, approval_required=True)
    b = _book(client, soc["res"], a["id"]).json()
    assert b["status"] == "pending"
    # A resident or a guard may not decide.
    for who in ("res2", "guard", "res"):
        assert client.post(f"{A}/bookings/{b['id']}/approve", json={}, headers=soc[who]["headers"]).status_code == 403
    pending = client.get(f"{A}/bookings/society/{soc['society'].id}/pending", headers=soc["admin"]["headers"]).json()
    assert [p["id"] for p in pending] == [b["id"]]
    ok = client.post(f"{A}/bookings/{b['id']}/approve", json={}, headers=soc["admin"]["headers"])
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    assert ok.json()["approved_by_name"] == "Asha Admin"
    # Deciding twice is refused.
    assert client.post(f"{A}/bookings/{b['id']}/approve", json={}, headers=soc["admin"]["headers"]).status_code == 409


def test_rejecting_needs_a_reason(client, soc):
    a = _amenity(client, soc, approval_required=True)
    b = _book(client, soc["res"], a["id"]).json()
    assert client.post(f"{A}/bookings/{b['id']}/reject", json={"reason": "  "}, headers=soc["admin"]["headers"]).status_code == 422
    r = client.post(f"{A}/bookings/{b['id']}/reject", json={"reason": "Maintenance"}, headers=soc["admin"]["headers"])
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert r.json()["rejection_reason"] == "Maintenance"


def test_approval_rechecks_that_the_date_is_still_open(client, soc):
    a = _amenity(client, soc, approval_required=True)
    b = _book(client, soc["res"], a["id"]).json()
    client.post(f"{A}/{a['id']}/blackouts", json={"blackout_date": _ahead(3)}, headers=soc["admin"]["headers"])
    r = client.post(f"{A}/bookings/{b['id']}/approve", json={}, headers=soc["admin"]["headers"])
    assert r.status_code == 409


# ── Cancelling and completing ─────────────────────────────────────────────────

def test_only_the_booker_or_the_committee_may_cancel(client, soc):
    a = _amenity(client, soc)
    b = _book(client, soc["res"], a["id"]).json()
    assert client.post(f"{A}/bookings/{b['id']}/cancel", json={}, headers=soc["res2"]["headers"]).status_code == 403
    assert client.post(f"{A}/bookings/{b['id']}/cancel", json={}, headers=soc["admin"]["headers"]).status_code == 200


def _past_booking(db, soc, amenity_id, status="approved"):
    from app.modules.amenity.models.amenity import AmenityBooking, BookingStatus
    from uuid import UUID
    b = AmenityBooking(amenity_id=UUID(amenity_id), society_id=soc["society"].id, booked_by=soc["res"]["user"].id,
                       booking_date=date.today(), start_time=time(0, 0), end_time=time(0, 30),
                       status=BookingStatus(status), guest_count=1)
    db.add(b); db.commit(); db.refresh(b)
    return b


def test_a_started_booking_cannot_be_cancelled_by_the_resident(client, soc, db):
    a = _amenity(client, soc, open_time=None, close_time=None)
    b = _past_booking(db, soc, a["id"])
    assert client.post(f"{A}/bookings/{b.id}/cancel", json={}, headers=soc["res"]["headers"]).status_code == 409


def test_complete_after_use_and_not_before(client, soc, db):
    a = _amenity(client, soc, open_time=None, close_time=None)
    future = _book(client, soc["res"], a["id"]).json()
    assert client.post(f"{A}/bookings/{future['id']}/complete", json={}, headers=soc["admin"]["headers"]).status_code == 409
    b = _past_booking(db, soc, a["id"])
    assert client.post(f"{A}/bookings/{b.id}/complete", json={"damage_noted": True},
                       headers=soc["admin"]["headers"]).status_code == 422
    r = client.post(f"{A}/bookings/{b.id}/complete", json={"damage_noted": True, "damage_notes": "Broken chair"},
                    headers=soc["admin"]["headers"])
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert client.post(f"{A}/bookings/{b.id}/complete", json={}, headers=soc["admin"]["headers"]).status_code == 409


# ── Prices ────────────────────────────────────────────────────────────────────

def test_charge_comes_from_the_rate_rule_or_the_default_rate(client, soc):
    hourly = _amenity(client, soc, name="Hall", is_chargeable=True)
    _rule(client, soc, hourly["id"], "charge_per_hour", "250")
    _rule(client, soc, hourly["id"], "deposit_required", "1000")
    b = _book(client, soc["res"], hourly["id"], start="10:00:00", end="12:30:00").json()
    assert b["charge_amount"] == 625.0 and b["deposit_amount"] == 1000.0

    flat = _amenity(client, soc, name="Terrace", is_chargeable=True)
    r = client.post(f"{A}/{flat['id']}/pricing", json={"label": "Standard", "flat_price": 800, "deposit_amount": 500,
                                                       "is_default": True}, headers=soc["admin"]["headers"])
    assert r.status_code == 201
    c = _book(client, soc["res"], flat["id"]).json()
    assert c["charge_amount"] == 800.0 and c["deposit_amount"] == 500.0

    free = _amenity(client, soc, name="Library")
    d = _book(client, soc["res"], free["id"]).json()
    assert d["charge_amount"] is None


def test_a_rate_is_validated_and_can_be_removed(client, soc):
    a = _amenity(client, soc, is_chargeable=True)
    h = soc["admin"]["headers"]
    assert client.post(f"{A}/{a['id']}/pricing", json={"label": " "}, headers=h).status_code == 422
    assert client.post(f"{A}/{a['id']}/pricing", json={"label": "X"}, headers=h).status_code == 422
    assert client.post(f"{A}/{a['id']}/pricing", json={"label": "X", "flat_price": -1}, headers=h).status_code == 422
    p = client.post(f"{A}/{a['id']}/pricing", json={"label": "X", "flat_price": 100}, headers=h).json()
    assert len(client.get(f"{A}/{a['id']}/pricing", headers=h).json()) == 1
    assert client.delete(f"{A}/pricing/{p['id']}", headers=h).status_code == 204
    assert client.get(f"{A}/{a['id']}/pricing", headers=h).json() == []


# ── Day view and lists ────────────────────────────────────────────────────────

def test_day_view_shows_taken_times_and_names_only_to_the_committee(client, soc):
    a = _amenity(client, soc)
    _book(client, soc["res"], a["id"], start="10:00:00", end="12:00:00")
    res2 = client.get(f"{A}/{a['id']}/day", params={"for_date": _ahead(3)}, headers=soc["res2"]["headers"]).json()
    assert res2["open_time"] == "06:00:00" and res2["closed"] is False
    assert len(res2["bookings"]) == 1 and res2["bookings"][0]["mine"] is False
    assert "booked_by_name" not in res2["bookings"][0]
    mine = client.get(f"{A}/{a['id']}/day", params={"for_date": _ahead(3)}, headers=soc["res"]["headers"]).json()
    assert mine["bookings"][0]["mine"] is True
    adm = client.get(f"{A}/{a['id']}/day", params={"for_date": _ahead(3)}, headers=soc["admin"]["headers"]).json()
    assert adm["bookings"][0]["booked_by_name"] == "Rohan Resident" and adm["bookings"][0]["flat"] == "A / 101"


def test_my_bookings_and_the_society_list_filters(client, soc):
    a = _amenity(client, soc)
    _book(client, soc["res"], a["id"], day=3)
    _book(client, soc["res2"], a["id"], day=4)
    mine = client.get(f"{A}/bookings/me/list", headers=soc["res"]["headers"]).json()
    assert len(mine) == 1 and mine[0]["amenity_name"] == "Clubhouse"
    allb = client.get(f"{A}/bookings/society/{soc['society'].id}", headers=soc["admin"]["headers"])
    assert len(allb.json()) == 2
    f = client.get(f"{A}/bookings/society/{soc['society'].id}", params={"date_from": _ahead(4)},
                   headers=soc["admin"]["headers"]).json()
    assert len(f) == 1
    assert client.get(f"{A}/bookings/society/{soc['society'].id}", headers=soc["res"]["headers"]).status_code == 403


def test_a_booking_is_visible_only_to_its_booker_and_the_committee(client, soc):
    a = _amenity(client, soc)
    b = _book(client, soc["res"], a["id"]).json()
    assert client.get(f"{A}/bookings/{b['id']}", headers=soc["res"]["headers"]).status_code == 200
    assert client.get(f"{A}/bookings/{b['id']}", headers=soc["admin"]["headers"]).status_code == 200
    assert client.get(f"{A}/bookings/{b['id']}", headers=soc["res2"]["headers"]).status_code == 404


# ── Societies apart ───────────────────────────────────────────────────────────

def test_another_society_cannot_see_or_touch_any_of_it(client, soc, db):
    a = _amenity(client, soc, approval_required=True)
    b = _book(client, soc["res"], a["id"]).json()
    other = make_society(db, "Other Society")
    stranger_admin = _member(db, "admin@other.test", "Society Admin", other)
    stranger_res = _member(db, "res@other.test", "Resident", other)
    h, rh = stranger_admin["headers"], stranger_res["headers"]
    assert client.get(f"{A}/{a['id']}", headers=h).status_code == 404
    assert client.get(f"{A}/society/{soc['society'].id}", headers=h).status_code == 403
    assert client.patch(f"{A}/{a['id']}", json={"name": "Hijack"}, headers=h).status_code == 404
    assert client.post(f"{A}/{a['id']}/rules", json={"rule_type": "max_guests", "rule_value": "1"}, headers=h).status_code == 404
    assert client.get(f"{A}/{a['id']}/day", params={"for_date": _ahead(3)}, headers=rh).status_code == 404
    assert _book(client, stranger_res, a["id"]).status_code == 404
    assert client.post(f"{A}/bookings/{b['id']}/approve", json={}, headers=h).status_code == 404
    assert client.post(f"{A}/bookings/{b['id']}/reject", json={"reason": "no"}, headers=h).status_code == 404
    assert client.post(f"{A}/bookings/{b['id']}/cancel", json={}, headers=h).status_code == 404
    assert client.get(f"{A}/bookings/society/{soc['society'].id}", headers=h).status_code == 403
    assert client.get(f"{A}/bookings/society/{soc['society'].id}/pending", headers=h).status_code == 403
    # An admin cannot create into another society by naming it.
    r = client.post(f"{A}/", json={"society_id": str(soc["society"].id), "name": "Fake", "amenity_type": "gym"}, headers=h)
    assert r.status_code == 403
