"""The gym attendance book: the Gym Trainer ticks the members of a flat in and out; who is inside now; weekly and monthly
reports. The gym is for the owners' side of the society only: tenants are never offered."""
from datetime import date, datetime, timedelta
from io import BytesIO

import pytest
from pdfminer.high_level import extract_text

from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.models.wing import Wing
from app.modules.gym.models.gym import GymVisit
from tests.conftest import make_flat, make_society, make_user, make_wing, place_in

API = "/api/v1/gym"


@pytest.fixture
def rig(db):
    society = make_society(db, "Gym Society")
    wing_a = make_wing(db, society.id, "A")
    wing_b = Wing(society_id=society.id, name="B", code="B")
    db.add(wing_b)
    db.commit()
    owned, rented = make_flat(db, wing_a.id, "101"), make_flat(db, wing_b.id, "202")
    people = {
        "asha": Resident(full_name="Asha Rao", flat_id=owned.id, resident_type=ResidentType.OWNER, is_primary=True),
        "vik": Resident(full_name="Vik Rao", flat_id=owned.id, resident_type=ResidentType.FAMILY),
        "tia": Resident(full_name="Tia Rao", flat_id=owned.id, resident_type=ResidentType.DEPENDENT),
        "gone": Resident(full_name="Moved Out", flat_id=owned.id, resident_type=ResidentType.FAMILY,
                         move_out_date=date.today() - timedelta(days=30)),
        "left": Resident(full_name="Deactivated", flat_id=owned.id, resident_type=ResidentType.FAMILY, is_active=False),
    }
    db.add_all(people.values())
    db.add(Tenant(full_name="Rita Tenant", flat_id=rented.id))
    trainer = make_user(db, "gym-trainer@x.test", role="Gym Trainer")
    manager = make_user(db, "gym-manager@x.test", role="Manager")
    resident = make_user(db, "gym-resident@x.test", role="Resident")
    guard = make_user(db, "gym-guard@x.test", role="Security Staff")
    for u in (trainer, manager, resident, guard):
        place_in(db, u, society)
    db.commit()
    return {"society": society, "owned": owned, "rented": rented, "people": people, "trainer": trainer["headers"],
            "manager": manager["headers"], "resident": resident["headers"], "guard": guard["headers"], "db": db}


def _members(client, rig, flat=None, headers=None):
    return client.get(f"{API}/flats/{(flat or rig['owned']).id}/members", headers=headers or rig["trainer"])


def _check_in(client, rig, *names, headers=None):
    ids = [str(rig["people"][n].id) for n in names]
    return client.post(f"{API}/check-in", json={"flat_id": str(rig["owned"].id), "resident_ids": ids},
                       headers=headers or rig["trainer"])


def _live(client, rig):
    r = client.get(f"{API}/live", headers=rig["trainer"])
    assert r.status_code == 200, r.text
    return r.json()


# ── who may be ticked in ──────────────────────────────────────────────────────────────────────────────────────────

def test_a_flat_offers_its_active_members_owner_first(client, rig):
    r = _members(client, rig)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["flat_label"] == "A-101" and body["let_to_tenants"] is False
    assert [m["name"] for m in body["members"]] == ["Asha Rao", "Tia Rao", "Vik Rao"]     # owner first; moved-out and deactivated left out
    assert {m["member_type"] for m in body["members"]} == {"owner", "family", "dependent"}
    assert not any(m["inside"] for m in body["members"])


def test_tenants_are_never_offered_and_the_flat_says_it_is_let(client, rig):
    body = _members(client, rig, flat=rig["rented"]).json()
    assert body["members"] == [] and body["let_to_tenants"] is True
    assert "Rita" not in str(body)


def test_a_flat_of_another_society_is_not_found(client, db, rig):
    other = make_society(db, "Other Gym Society")
    far_flat = make_flat(db, make_wing(db, other.id, "Z").id, "9")
    assert _members(client, rig, flat=far_flat).status_code == 404


# ── ticking in and out ────────────────────────────────────────────────────────────────────────────────────────────

def test_ticking_two_members_in_shows_them_inside_and_counts_them(client, rig):
    r = _check_in(client, rig, "asha", "vik")
    assert r.status_code == 200, r.text
    assert sorted(v["name"] for v in r.json()["checked_in"]) == ["Asha Rao", "Vik Rao"] and r.json()["already_inside"] == []
    live = _live(client, rig)
    assert (live["inside_now"], live["checked_in_today"], live["checked_out_today"]) == (2, 2, 0)
    assert sorted(v["name"] for v in live["inside"]) == ["Asha Rao", "Vik Rao"]
    assert all(v["flat_label"] == "A-101" and v["minutes_inside"] >= 0 for v in live["inside"])
    # The flat's list now shows who is inside, so the trainer cannot tick them twice.
    inside = {m["name"]: m["inside"] for m in _members(client, rig).json()["members"]}
    assert inside == {"Asha Rao": True, "Tia Rao": False, "Vik Rao": True}


def test_ticking_someone_already_inside_does_not_count_them_twice(client, rig):
    _check_in(client, rig, "asha")
    r = _check_in(client, rig, "asha", "tia").json()
    assert [v["name"] for v in r["checked_in"]] == ["Tia Rao"] and r["already_inside"] == ["Asha Rao"]
    live = _live(client, rig)
    assert (live["inside_now"], live["checked_in_today"]) == (2, 2)


def test_only_members_of_that_flat_can_be_ticked_in(client, rig, db):
    stranger = Resident(full_name="Other Flat Person", flat_id=rig["rented"].id, resident_type=ResidentType.OWNER)
    db.add(stranger)
    db.commit()
    r = client.post(f"{API}/check-in", json={"flat_id": str(rig["owned"].id), "resident_ids": [str(stranger.id)]},
                    headers=rig["trainer"])
    assert r.status_code == 422
    r = _check_in(client, rig, "gone")                                  # moved out
    assert r.status_code == 422
    assert _live(client, rig)["inside_now"] == 0


def test_a_tenant_cannot_be_ticked_in_even_by_id(client, rig, db):
    tenant = db.query(Tenant).filter_by(full_name="Rita Tenant").one()
    r = client.post(f"{API}/check-in", json={"flat_id": str(rig["rented"].id), "resident_ids": [str(tenant.id)]},
                    headers=rig["trainer"])
    assert r.status_code == 422


def test_ticking_in_needs_at_least_one_member(client, rig):
    r = client.post(f"{API}/check-in", json={"flat_id": str(rig["owned"].id), "resident_ids": []}, headers=rig["trainer"])
    assert r.status_code == 422


def test_ticking_out_one_member_then_everyone(client, rig):
    first = _check_in(client, rig, "asha", "vik", "tia").json()["checked_in"]
    leaving = next(v["visit_id"] for v in first if v["name"] == "Vik Rao")
    r = client.post(f"{API}/check-out", json={"visit_ids": [leaving]}, headers=rig["trainer"])
    assert r.status_code == 200 and r.json()["checked_out"] == 1
    live = _live(client, rig)
    assert (live["inside_now"], live["checked_in_today"], live["checked_out_today"]) == (2, 3, 1)
    assert "Vik Rao" not in [v["name"] for v in live["inside"]]
    # Ticking the same person out again changes nothing.
    assert client.post(f"{API}/check-out", json={"visit_ids": [leaving]}, headers=rig["trainer"]).json()["checked_out"] == 0
    # Closing time.
    assert client.post(f"{API}/check-out-all", headers=rig["trainer"]).json()["checked_out"] == 2
    live = _live(client, rig)
    assert (live["inside_now"], live["checked_out_today"]) == (0, 3)
    # And the same member can come back later.
    assert _check_in(client, rig, "vik").status_code == 200 and _live(client, rig)["inside_now"] == 1


def test_an_unknown_or_foreign_visit_is_not_found(client, db, rig):
    r = client.post(f"{API}/check-out", json={"visit_ids": ["00000000-0000-0000-0000-000000000001"]}, headers=rig["trainer"])
    assert r.status_code == 404
    other = make_society(db, "Foreign Gym Society")
    foreign = GymVisit(society_id=other.id, member_name="Far Away", flat_label="Z-1", checked_in_at=datetime.utcnow())
    db.add(foreign)
    db.commit()
    r = client.post(f"{API}/check-out", json={"visit_ids": [str(foreign.id)]}, headers=rig["trainer"])
    assert r.status_code == 404
    db.refresh(foreign)
    assert foreign.checked_out_at is None
    assert _live(client, rig)["inside_now"] == 0                         # and it is not in this society's count


# ── forgotten check-outs ──────────────────────────────────────────────────────────────────────────────────────────

def test_a_visit_nobody_ticked_out_yesterday_is_not_counted_as_inside_and_can_be_closed(client, db, rig):
    old = GymVisit(society_id=rig["society"].id, flat_id=rig["owned"].id, resident_id=rig["people"]["asha"].id,
                   member_name="Asha Rao", flat_label="A-101", checked_in_at=datetime.utcnow() - timedelta(hours=40))
    db.add(old)
    db.commit()
    live = _live(client, rig)
    assert live["inside_now"] == 0 and [v["name"] for v in live["earlier_open"]] == ["Asha Rao"]
    assert _check_in(client, rig, "asha").status_code == 200                # she can be ticked in again today
    assert client.post(f"{API}/check-out", json={"visit_ids": [str(old.id)]}, headers=rig["trainer"]).json()["checked_out"] == 1
    db.refresh(old)
    assert old.checked_out_at is not None and old.closed_late is True
    assert _live(client, rig)["earlier_open"] == []


# ── the reports ───────────────────────────────────────────────────────────────────────────────────────────────────

def _visit(db, rig, who, day, hour_in, minutes=None, **extra):
    """A visit on `day` at `hour_in` UTC (15:30 IST + ...), left `minutes` later (None: never ticked out)."""
    p = rig["people"][who]
    t_in = datetime(day.year, day.month, day.day, hour_in, 0)
    v = GymVisit(society_id=rig["society"].id, flat_id=p.flat_id, resident_id=p.id, member_name=p.full_name,
                 flat_label="A-101", member_type="owner", checked_in_at=t_in,
                 checked_out_at=t_in + timedelta(minutes=minutes) if minutes is not None else None, **extra)
    db.add(v)
    return v


@pytest.fixture
def march(db, rig):
    # Week Monday 9 Mar to Sunday 15 Mar 2026, inside March 2026.
    _visit(db, rig, "asha", date(2026, 3, 9), 2, 60)
    _visit(db, rig, "vik", date(2026, 3, 9), 3, 30)
    _visit(db, rig, "asha", date(2026, 3, 11), 2, 90)
    _visit(db, rig, "asha", date(2026, 3, 15), 2, None)            # never ticked out
    _visit(db, rig, "tia", date(2026, 3, 20), 2, 45)                # next week, same month
    _visit(db, rig, "vik", date(2026, 2, 27), 2, 30)                # last month
    db.commit()
    return rig


def test_the_weekly_report_covers_monday_to_sunday(client, march):
    r = client.get(f"{API}/report", params={"period": "week", "on": "2026-03-11"}, headers=march["trainer"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["from"], body["to"]) == ("2026-03-09", "2026-03-15") and len(body["days"]) == 7
    assert body["totals"]["visits"] == 4 and body["totals"]["unique_members"] == 2 and body["totals"]["unique_flats"] == 1
    assert body["totals"]["average_minutes"] == 60                       # (60 + 30 + 90) / 3 ticked-out visits
    assert body["totals"]["not_checked_out"] == 1 and body["totals"]["busiest_day"] == "2026-03-09"
    by_day = {d["date"]: d["visits"] for d in body["days"]}
    assert by_day["2026-03-09"] == 2 and by_day["2026-03-11"] == 1 and by_day["2026-03-15"] == 1 and by_day["2026-03-10"] == 0
    assert [(m["name"], m["visits"], m["total_minutes"]) for m in body["members"]] == [("Asha Rao", 3, 150), ("Vik Rao", 1, 30)]


def test_the_monthly_report_covers_the_calendar_month(client, march):
    body = client.get(f"{API}/report", params={"period": "month", "on": "2026-03-11"}, headers=march["trainer"]).json()
    assert (body["from"], body["to"], body["label"]) == ("2026-03-01", "2026-03-31", "March 2026") and len(body["days"]) == 31
    assert body["totals"]["visits"] == 5 and body["totals"]["unique_members"] == 3          # February's visit is not in it
    assert [m["name"] for m in body["members"]] == ["Asha Rao", "Tia Rao", "Vik Rao"]
    feb = client.get(f"{API}/report", params={"period": "month", "on": "2026-02-10"}, headers=march["trainer"]).json()
    assert (feb["to"], feb["totals"]["visits"]) == ("2026-02-28", 1)


def test_a_late_closed_visit_counts_as_a_visit_but_has_no_length(client, db, rig):
    _visit(db, rig, "asha", date(2026, 3, 9), 2, 500, closed_late=True)
    db.commit()
    body = client.get(f"{API}/report", params={"period": "week", "on": "2026-03-09"}, headers=rig["trainer"]).json()
    assert body["totals"]["visits"] == 1 and body["totals"]["average_minutes"] is None
    assert body["totals"]["not_checked_out"] == 1 and body["members"][0]["total_minutes"] == 0


def test_the_report_is_the_societys_own_and_keeps_names_as_they_were(client, db, rig, march):
    other = make_society(db, "Foreign Report Society")
    db.add(GymVisit(society_id=other.id, member_name="Far Away", flat_label="Z-1", checked_in_at=datetime(2026, 3, 10, 5, 0)))
    march["people"]["asha"].full_name = "Asha Renamed"                   # renamed afterwards
    db.commit()
    body = client.get(f"{API}/report", params={"period": "week", "on": "2026-03-11"}, headers=march["trainer"]).json()
    names = [m["name"] for m in body["members"]]
    assert "Far Away" not in names and "Asha Rao" in names and "Asha Renamed" not in names


def test_the_report_can_be_printed(client, march):
    r = client.get(f"{API}/report", params={"period": "week", "on": "2026-03-11", "format": "pdf"}, headers=march["trainer"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    text = extract_text(BytesIO(r.content))
    assert "GYM ATTENDANCE REPORT" in text and "Asha Rao" in text and "Vik Rao" in text and "Tia Rao" not in text
    assert "Week of 09 Mar 2026 to 15 Mar 2026" in text


def test_an_empty_period_still_gives_a_report(client, rig):
    body = client.get(f"{API}/report", params={"period": "month", "on": "2030-01-05"}, headers=rig["trainer"]).json()
    assert body["totals"]["visits"] == 0 and body["members"] == [] and body["totals"]["busiest_day"] is None
    pdf = client.get(f"{API}/report", params={"period": "month", "on": "2030-01-05", "format": "pdf"}, headers=rig["trainer"])
    assert "Nobody used the gym in this period." in extract_text(BytesIO(pdf.content))


def test_a_bad_period_is_refused(client, rig):
    assert client.get(f"{API}/report", params={"period": "year"}, headers=rig["trainer"]).status_code == 422


# ── who may keep the book ─────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("who", ["trainer", "manager"])
def test_the_gym_trainer_and_the_manager_can_use_the_book(client, rig, who):
    assert client.get(f"{API}/live", headers=rig[who]).status_code == 200
    assert _members(client, rig, headers=rig[who]).status_code == 200
    assert _check_in(client, rig, "asha", headers=rig[who]).status_code == 200


@pytest.mark.parametrize("who", ["resident", "guard"])
def test_a_resident_and_a_guard_cannot(client, rig, who):
    h = rig[who]
    assert client.get(f"{API}/live", headers=h).status_code == 403
    assert _members(client, rig, headers=h).status_code == 403
    assert _check_in(client, rig, "asha", headers=h).status_code == 403
    assert client.post(f"{API}/check-out-all", headers=h).status_code == 403
    assert client.get(f"{API}/report", headers=h).status_code == 403


def test_a_login_is_needed(client, rig):
    assert client.get(f"{API}/live").status_code in (401, 403)
    assert client.post(f"{API}/check-in", json={}).status_code in (401, 403)
