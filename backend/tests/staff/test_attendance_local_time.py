"""Daily in/out on the society's own clock.

Timestamps are stored as UTC, but the date of a punch, a shift's start and the
overnight shift are all the society's local time: a guard who punches in at
22:00 and out at 06:00 must be able to check out, a 9:00 AM punch must read
9:00 AM in the app, and "late" must be judged against the shift in local time.
"""
from datetime import date, datetime, time, timedelta
from uuid import UUID

import pytest

from app.utils.local_time import local_to_utc_naive, local_today, zone
from tests.conftest import link_staff_login, make_society, make_user

S = "/api/v1/staff"
IST = zone("Asia/Kolkata")


def _staff(client, headers, society_id, name, mobile, dept="security"):
    r = client.post(f"{S}/", json={"society_id": str(society_id), "full_name": name, "mobile": mobile,
                                   "email": f"{mobile}@att.io", "department": dept}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def rig(db, client):
    admin = make_user(db, "att-admin@loc.io", role="Society Admin")
    society = make_society(db, "Local Time Society")
    guard = _staff(client, admin["headers"], society.id, "Night Guard", "9822100001")
    login = make_user(db, "att-guard@loc.io", role="Security Staff")
    link_staff_login(db, guard["id"], login)
    return {"admin": admin["headers"], "society": society, "sid": society.id, "guard": guard,
            "me": login["headers"], "gid": UUID(guard["id"])}


def _seed(db, rig, check_in, check_out=None, day=None, **over):
    from app.modules.staff.models.staff import AttendanceStatus, StaffAttendance
    rec = StaffAttendance(society_id=rig["sid"], staff_id=over.pop("staff_id", rig["gid"]),
                          attendance_date=day or local_today(IST), status=AttendanceStatus.PRESENT,
                          check_in_time=check_in, check_out_time=check_out, **over)
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


def _in(client, rig, headers=None):
    return client.post(f"{S}/attendance/{rig['guard']['id']}/checkin", json={}, headers=headers or rig["me"])


def _out(client, rig, headers=None):
    return client.post(f"{S}/attendance/{rig['guard']['id']}/checkout", json={}, headers=headers or rig["me"])


def _why(r):
    return str(r.json())


# ── What the app receives ─────────────────────────────────────────────────────

def test_times_are_sent_as_utc_with_a_z_so_the_app_shows_local_time(client, rig):
    before = datetime.utcnow().replace(microsecond=0) - timedelta(seconds=1)
    r = _in(client, rig)
    assert r.status_code == 200, r.text
    stamp = r.json()["check_in_time"]
    assert stamp.endswith("Z")
    sent = datetime.fromisoformat(stamp.replace("Z", "+00:00")).replace(tzinfo=None)
    assert before <= sent <= datetime.utcnow() + timedelta(seconds=2)
    out = _out(client, rig).json()
    assert out["check_out_time"].endswith("Z") and out["approved_at"] is None


# ── The date of a punch is the society's date ────────────────────────────────

@pytest.mark.parametrize("tz_name", ["Pacific/Kiritimati", "Pacific/Pago_Pago"])
def test_the_punch_date_follows_the_societys_clock(client, db, rig, tz_name):
    # +14 and -11 hours: at any moment at least one of them is on a different date from UTC
    rig["society"].timezone = tz_name
    db.commit()
    assert _in(client, rig).json()["attendance_date"] == str(local_today(zone(tz_name)))


# ── Night shifts ──────────────────────────────────────────────────────────────

def test_a_night_guard_can_check_out_the_next_morning(client, db, rig):
    began = datetime.utcnow() - timedelta(hours=8)
    rec = _seed(db, rig, began, day=local_today(IST) - timedelta(days=1))
    r = _out(client, rig)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(rec.id) and 7.9 <= r.json()["working_hours"] <= 8.1
    from app.modules.staff.models.staff import StaffAttendance
    assert db.query(StaffAttendance).filter(StaffAttendance.staff_id == rig["gid"]).count() == 1


def test_you_cannot_check_in_again_while_still_checked_in(client, db, rig):
    _seed(db, rig, datetime.utcnow() - timedelta(hours=3), day=local_today(IST) - timedelta(days=1))
    r = _in(client, rig)
    assert r.status_code == 409 and "Check out first" in _why(r)


def test_a_forgotten_punch_out_from_long_ago_does_not_block_a_new_day(client, db, rig):
    stale = _seed(db, rig, datetime.utcnow() - timedelta(hours=30), day=local_today(IST) - timedelta(days=2))
    assert _in(client, rig).status_code == 200
    closed = _out(client, rig).json()
    assert closed["id"] != str(stale.id)


def test_checking_out_needs_a_check_in_and_cannot_be_done_twice(client, rig):
    assert _out(client, rig).status_code == 404
    _in(client, rig)
    assert _out(client, rig).status_code == 200
    again = _out(client, rig)
    assert again.status_code == 409 and "Already checked out" in _why(again)


# ── Late is judged on the society's clock ────────────────────────────────────

def test_late_is_measured_against_the_shift_in_local_time(client, db, rig):
    from app.modules.staff.models.staff import StaffShift, Staff
    shift = StaffShift(society_id=rig["sid"], name="General", start_time=time(9, 0), end_time=time(17, 0))
    db.add(shift); db.commit()
    punctual = db.query(Staff).filter(Staff.id == rig["gid"]).one()
    late = _staff(client, rig["admin"], rig["sid"], "Late Guard", "9822100002")
    for s in (punctual, db.query(Staff).filter(Staff.id == UUID(late["id"])).one()):
        s.shift_id = shift.id
    db.commit()
    day = local_today(IST) - timedelta(days=1)
    _seed(db, rig, local_to_utc_naive(day, time(9, 10), IST), day=day)                      # 10 minutes after the start
    _seed(db, rig, local_to_utc_naive(day, time(10, 0), IST), day=day, staff_id=UUID(late["id"]))   # an hour after
    summary = client.get(f"{S}/society/{rig['sid']}/summary?att_date={day}", headers=rig["admin"]).json()
    assert summary["present"] == 2 and summary["late"] == 1


# ── A rejected punch is not attendance ────────────────────────────────────────

def test_a_rejected_punch_in_does_not_count_as_present(client, db, rig):
    sup = make_user(db, "att-sup@loc.io", role="Security Supervisor")["headers"]
    att = _in(client, rig).json()
    day = att["attendance_date"]
    assert client.get(f"{S}/attendance/daily/{rig['sid']}?att_date={day}", headers=rig["admin"]).json() != []
    assert client.post(f"{S}/attendance/{att['id']}/reject", json={"reason": "not at the gate"}, headers=sup).status_code == 200
    assert client.get(f"{S}/attendance/daily/{rig['sid']}?att_date={day}", headers=rig["admin"]).json() == []
    assert client.get(f"{S}/society/{rig['sid']}/summary?att_date={day}", headers=rig["admin"]).json()["present"] == 0
    assert _in(client, rig).status_code == 200


def test_a_supervisors_summary_covers_only_their_department(client, db, rig):
    sup = make_user(db, "att-sup2@loc.io", role="Security Supervisor")
    record = _staff(client, rig["admin"], rig["sid"], "Sup Two", "9822100003")
    link_staff_login(db, record["id"], sup)
    cleaner = _staff(client, rig["admin"], rig["sid"], "Cleaner", "9822100004", "housekeeping")
    day = local_today(IST)
    _seed(db, rig, datetime.utcnow(), day=day)
    _seed(db, rig, datetime.utcnow(), day=day, staff_id=UUID(cleaner["id"]))
    everyone = client.get(f"{S}/society/{rig['sid']}/summary?att_date={day}", headers=rig["admin"]).json()
    own = client.get(f"{S}/society/{rig['sid']}/summary?att_date={day}", headers=sup["headers"]).json()
    assert everyone["total_staff"] == 3 and everyone["present"] == 2
    assert own["total_staff"] == 2 and own["present"] == 1 and set(own["department_breakdown"]) == {"security"}


# ── Manual entry ──────────────────────────────────────────────────────────────

def test_manual_times_without_a_zone_are_the_societys_clock(client, rig):
    day = local_today(IST) - timedelta(days=1)
    r = client.post(f"{S}/attendance/manual", headers=rig["admin"], json={
        "staff_id": rig["guard"]["id"], "society_id": str(rig["sid"]), "attendance_date": str(day),
        "status": "present", "check_in_time": f"{day}T09:00:00", "check_out_time": f"{day}T17:00:00"})
    assert r.status_code == 200, r.text
    assert r.json()["check_in_time"] == f"{day}T03:30:00Z" and r.json()["check_out_time"] == f"{day}T11:30:00Z"
    # the same moment given with its own offset is the same time
    day2 = day - timedelta(days=1)
    r2 = client.post(f"{S}/attendance/manual", headers=rig["admin"], json={
        "staff_id": rig["guard"]["id"], "society_id": str(rig["sid"]), "attendance_date": str(day2),
        "status": "present", "check_in_time": f"{day2}T09:00:00+05:30"})
    assert r2.json()["check_in_time"] == f"{day2}T03:30:00Z"


def test_todays_date_in_india_is_not_a_future_date(client, rig):
    # just after midnight in India the UTC date is still yesterday: today must be accepted
    r = client.post(f"{S}/attendance/manual", headers=rig["admin"], json={
        "staff_id": rig["guard"]["id"], "society_id": str(rig["sid"]),
        "attendance_date": str(local_today(IST)), "status": "present"})
    assert r.status_code == 200, r.text
    tomorrow = client.post(f"{S}/attendance/manual", headers=rig["admin"], json={
        "staff_id": rig["guard"]["id"], "society_id": str(rig["sid"]),
        "attendance_date": str(local_today(IST) + timedelta(days=1)), "status": "present"})
    assert tomorrow.status_code == 422
