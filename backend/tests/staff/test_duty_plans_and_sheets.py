"""Duty plans, department scope, printable sheets and paper-sheet entry.

A plan gives one duty to several staff over a range of days (every day or chosen
weekdays). A department supervisor works only with their own department's staff.
A printed sheet is filled in on paper and a supervisor enters it in the app; every
item keeps who entered it and that it came from paper.
"""
import re
from datetime import date, datetime, time, timedelta

import pytest

from tests.conftest import make_society, make_user

S = "/api/v1/staff"
# A Monday well in the past, so paper sheets for it are never "future".
MON = date(2026, 9, 7)


def _staff(client, headers, society_id, name, mobile, dept="security"):
    r = client.post(f"{S}/", json={"society_id": str(society_id), "full_name": name, "mobile": mobile,
                                   "email": f"{mobile}@duty.io", "department": dept}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _template(client, headers, society_id, dept="security", name="Gate Round"):
    r = client.post(f"{S}/checklist-templates", headers=headers, json={
        "society_id": str(society_id), "department": dept, "name": name,
        "items": [{"title": "Check main gate lock", "sequence": 0, "is_required": True},
                  {"title": "Log visitor book", "sequence": 1, "is_required": True},
                  {"title": "Inspect CCTV feed", "sequence": 2, "is_required": False}]})
    assert r.status_code == 201, r.text
    return r.json()


def _why(r) -> str:
    """The error text of a response, whichever envelope carried it."""
    return str(r.json())


def _plan(society_id, staff_ids, **over):
    body = {"society_id": str(society_id), "staff_ids": [str(s) for s in staff_ids], "duty_name": "Gate round",
            "from_date": str(MON), "to_date": str(MON + timedelta(days=6))}
    body.update(over)
    return body


def _supervisor(db, client, admin_headers, society_id):
    """A Security Supervisor who is also a staff record in the security department."""
    from tests.conftest import link_staff_login
    login = make_user(db, "plan-sec-sup@duty.io", role="Security Supervisor")
    record = _staff(client, admin_headers, society_id, "Sup One", "9811000010")
    link_staff_login(db, record["id"], login)
    return login["headers"]


@pytest.fixture
def rig(db, client):
    admin = make_user(db, "plan-admin@duty.io", role="Society Admin")
    society = make_society(db, "Plan Society")
    h = admin["headers"]
    return {
        "admin": h, "society": society, "sid": society.id,
        "g1": _staff(client, h, society.id, "Guard One", "9811000001"),
        "g2": _staff(client, h, society.id, "Guard Two", "9811000002"),
        "hk": _staff(client, h, society.id, "Cleaner One", "9811000003", "housekeeping"),
        "tpl": _template(client, h, society.id),
        "sup": _supervisor(db, client, h, society.id),
        "committee": make_user(db, "plan-cm@duty.io", role="Committee Member")["headers"],
    }


def _duties(client, headers, staff_id):
    r = client.get(f"{S}/duties/me/{staff_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── Plans ─────────────────────────────────────────────────────────────────────

def test_a_plan_makes_one_duty_per_staff_per_chosen_weekday_with_its_own_checklist(client, rig):
    r = client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig["g1"]["id"], rig["g2"]["id"]], weekdays=[0, 2, 4],
        checklist_template_id=rig["tpl"]["id"], start_time="22:00:00", end_time="23:00:00"))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["created"] == 6 and out["skipped"] == []
    assert out["first_date"] == str(MON) and out["last_date"] == str(MON + timedelta(days=4))

    duties = _duties(client, rig["admin"], rig["g1"]["id"])
    assert sorted(d["duty_date"] for d in duties) == [str(MON), str(MON + timedelta(days=2)), str(MON + timedelta(days=4))]
    assert {d["series_id"] for d in duties} == {out["series_id"]}
    assert all(d["is_recurring"] and len(d["checklist_items"]) == 3 for d in duties)
    # each day has its own copy: ticking one day's item leaves the others alone
    first, other = duties[0], duties[1]
    client.post(f"{S}/duties/{first['id']}/checklist/{first['checklist_items'][0]['id']}/complete",
                json={"is_completed": True}, headers=rig["admin"])
    again = {d["id"]: d for d in _duties(client, rig["admin"], rig["g1"]["id"])}
    assert again[first["id"]]["checklist_items"][0]["is_completed"] is True
    assert again[other["id"]]["checklist_items"][0]["is_completed"] is False


def test_a_single_day_plan_is_not_recurring_and_every_day_is_the_default(client, rig):
    one = client.post(f"{S}/duties/plan", headers=rig["admin"], json={
        "society_id": str(rig["sid"]), "staff_ids": [rig["g1"]["id"]], "duty_name": "Fire drill",
        "from_date": str(MON)}).json()
    assert one["created"] == 1
    assert _duties(client, rig["admin"], rig["g1"]["id"])[0]["is_recurring"] is False

    week = client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig["g2"]["id"]], duty_name="Round")).json()
    assert week["created"] == 7


def test_leave_and_duplicates_are_skipped_and_reported(client, db, rig):
    from app.modules.staff.models.staff import LeaveStatus, LeaveType, StaffLeave
    from uuid import UUID
    db.add(StaffLeave(society_id=rig["sid"], staff_id=UUID(rig["g1"]["id"]), leave_type=LeaveType.CASUAL,
                      from_date=MON + timedelta(days=1), to_date=MON + timedelta(days=2), total_days=2,
                      status=LeaveStatus.APPROVED))
    db.commit()
    body = _plan(rig["sid"], [rig["g1"]["id"]], to_date=str(MON + timedelta(days=3)))
    out = client.post(f"{S}/duties/plan", headers=rig["admin"], json=body).json()
    assert out["created"] == 2
    assert sorted(s["duty_date"] for s in out["skipped"]) == [str(MON + timedelta(days=1)), str(MON + timedelta(days=2))]
    assert {s["reason"] for s in out["skipped"]} == {"On approved leave"}

    # the same plan again: the two days already planned are skipped, nothing is doubled
    again = client.post(f"{S}/duties/plan", headers=rig["admin"], json=body).json()
    assert again["created"] == 0
    assert {s["reason"] for s in again["skipped"] if s["duty_date"] in (str(MON), str(MON + timedelta(days=3)))} == \
        {"Already has this duty on that day"}
    assert len(_duties(client, rig["admin"], rig["g1"]["id"])) == 2


def test_plan_ranges_are_checked(client, db, rig):
    base = _plan(rig["sid"], [rig["g1"]["id"]])
    assert client.post(f"{S}/duties/plan", headers=rig["admin"],
                       json={**base, "to_date": str(MON - timedelta(days=1))}).status_code == 422
    assert client.post(f"{S}/duties/plan", headers=rig["admin"],
                       json={**base, "to_date": str(MON + timedelta(days=62))}).status_code == 422
    assert client.post(f"{S}/duties/plan", headers=rig["admin"],
                       json={**base, "weekdays": [7]}).status_code == 422
    assert client.post(f"{S}/duties/plan", headers=rig["admin"],
                       json={**base, "staff_ids": []}).status_code == 422
    # a Monday-only plan over Tue-Sun has no day to make
    r = client.post(f"{S}/duties/plan", headers=rig["admin"], json={
        **base, "from_date": str(MON + timedelta(days=1)), "to_date": str(MON + timedelta(days=6)), "weekdays": [0]})
    assert r.status_code == 422 and "weekdays" in _why(r)
    assert _duties(client, rig["admin"], rig["g1"]["id"]) == []


def test_a_plan_cannot_reach_other_societies_staff_or_templates(client, db, rig):
    other = make_society(db, "Other Society")
    foreign = _staff(client, rig["admin"], other.id, "Foreign Guard", "9811000009")
    r = client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(rig["sid"], [foreign["id"]]))
    assert r.status_code == 422
    foreign_tpl = _template(client, rig["admin"], other.id, name="Foreign Round")
    r = client.post(f"{S}/duties/plan", headers=rig["admin"],
                    json=_plan(rig["sid"], [rig["g1"]["id"]], checklist_template_id=foreign_tpl["id"]))
    assert r.status_code == 404


# ── A supervisor works with their own department ─────────────────────────────

def test_a_supervisor_assigns_only_to_their_own_department(client, rig):
    sup = rig["sup"]
    assert client.post(f"{S}/duties/plan", headers=sup,
                       json=_plan(rig["sid"], [rig["g1"]["id"]])).status_code == 201
    r = client.post(f"{S}/duties/plan", headers=sup, json=_plan(rig["sid"], [rig["hk"]["id"]]))
    assert r.status_code == 403 and "housekeeping" in _why(r)
    # a mixed plan is refused whole, not half-made
    assert client.post(f"{S}/duties/plan", headers=sup,
                       json=_plan(rig["sid"], [rig["g2"]["id"], rig["hk"]["id"]])).status_code == 403
    assert _duties(client, rig["admin"], rig["g2"]["id"]) == []
    # the single-duty route has the same rule
    single = {"society_id": str(rig["sid"]), "staff_id": rig["hk"]["id"], "duty_name": "Sweep", "duty_date": str(MON)}
    assert client.post(f"{S}/duties", headers=sup, json=single).status_code == 403


def test_a_supervisor_verifies_only_their_own_departments_duties(client, rig):
    sup, admin = rig["sup"], rig["admin"]
    d = client.post(f"{S}/duties", headers=admin, json={
        "society_id": str(rig["sid"]), "staff_id": rig["hk"]["id"], "duty_name": "Sweep", "duty_date": str(MON)}).json()
    client.post(f"{S}/duties/{d['id']}/complete", headers=admin)
    assert client.post(f"{S}/duties/{d['id']}/verify", json={}, headers=sup).status_code == 403
    assert client.post(f"{S}/duties/{d['id']}/verify", json={}, headers=admin).status_code == 200


def test_committee_members_and_managers_assign_across_departments(client, rig):
    out = client.post(f"{S}/duties/plan", headers=rig["committee"],
                      json=_plan(rig["sid"], [rig["g1"]["id"], rig["hk"]["id"]], to_date=str(MON)))
    assert out.status_code == 201 and out.json()["created"] == 2


# ── Printable sheets ──────────────────────────────────────────────────────────

def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b(?!s)", pdf))


def _text(pdf: bytes) -> str:
    runs = re.findall(rb"\((.*?)\) Tj", pdf)
    return "|".join(r.decode("latin1").replace("\\(", "(").replace("\\)", ")") for r in runs)


def _planned(client, rig, **over):
    r = client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig["g1"]["id"], rig["g2"]["id"]], checklist_template_id=rig["tpl"]["id"],
        location="Main gate", start_time="22:00:00", end_time="23:00:00", **over))
    assert r.status_code == 201, r.text


def test_the_society_sheet_is_one_page_per_staff_per_day(client, rig):
    _planned(client, rig, to_date=str(MON + timedelta(days=2)))
    one_day = client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={MON}", headers=rig["admin"])
    assert one_day.status_code == 200 and one_day.headers["content-type"] == "application/pdf"
    assert one_day.content.startswith(b"%PDF") and _pages(one_day.content) == 2
    three_days = client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={MON}&to_date={MON + timedelta(days=2)}",
                            headers=rig["admin"])
    assert _pages(three_days.content) == 6
    assert client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={MON}&to_date={MON + timedelta(days=7)}",
                      headers=rig["admin"]).status_code == 422


def test_the_sheet_prints_the_duty_its_checklist_and_the_blank_in_out_strip(db, client, rig):
    from app.modules.staff.models.staff import DutyAssignment, Staff
    from app.modules.staff.services.duty_sheet_pdf import render_duty_sheets
    from app.utils.local_time import zone
    _planned(client, rig, to_date=str(MON))
    duty = db.query(DutyAssignment).filter(DutyAssignment.duty_name == "Gate round").first()
    page = {"staff": duty.staff, "date": duty.duty_date, "duties": [duty]}
    text = _text(render_duty_sheets(rig["society"], zone("Asia/Kolkata"), [page], compress=False))
    for expected in ("DAILY DUTY SHEET", "Guard One", "Mon, 07 Sep 2026", "Gate round", "Main gate", "22:00",
                     "23:00", "Check main gate lock", "Log visitor book", "Inspect CCTV feed", "IN time", "OUT time",
                     "Staff signature", "Supervisor signature"):
        assert expected in text, expected
    # the two required items carry the star, the optional one doesn't
    assert "Check main gate lock |*" in text and "Log visitor book |*" in text
    assert "Inspect CCTV feed|*" not in text and "Inspect CCTV feed |*" not in text


def test_the_department_filter_and_a_supervisors_own_department(client, rig):
    _planned(client, rig, to_date=str(MON))
    client.post(f"{S}/duties", headers=rig["admin"], json={
        "society_id": str(rig["sid"]), "staff_id": rig["hk"]["id"], "duty_name": "Sweep", "duty_date": str(MON)})
    base = f"{S}/duties/sheet/society/{rig['sid']}?duty_date={MON}"
    assert _pages(client.get(base, headers=rig["admin"]).content) == 3
    assert _pages(client.get(base + "&department=housekeeping", headers=rig["admin"]).content) == 1
    # a security supervisor is held to security whatever they ask for
    assert _pages(client.get(base + "&department=housekeeping", headers=rig["sup"]).content) == 2
    assert client.get(base + "&department=nonsense", headers=rig["admin"]).status_code == 400


def test_nothing_to_print_says_so(client, rig):
    r = client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={MON}", headers=rig["admin"])
    assert r.status_code == 404 and "nothing to print" in _why(r)


def test_staff_print_their_own_sheet_but_not_a_colleagues(client, db, rig):
    from tests.conftest import link_staff_login
    guard = make_user(db, "own-sheet@duty.io", role="Security Staff")
    colleague = make_user(db, "other-sheet@duty.io", role="Security Staff")
    link_staff_login(db, rig["g1"]["id"], guard)
    link_staff_login(db, rig["g2"]["id"], colleague)
    _planned(client, rig, to_date=str(MON))
    mine = client.get(f"{S}/duties/sheet/staff/{rig['g1']['id']}?duty_date={MON}", headers=guard["headers"])
    assert mine.status_code == 200 and _pages(mine.content) == 1
    assert client.get(f"{S}/duties/sheet/staff/{rig['g2']['id']}?duty_date={MON}",
                      headers=guard["headers"]).status_code == 403
    # a supervisor prints a colleague's, but not another department's
    assert client.get(f"{S}/duties/sheet/staff/{rig['g2']['id']}?duty_date={MON}",
                      headers=rig["sup"]).status_code == 200
    client.post(f"{S}/duties", headers=rig["admin"], json={
        "society_id": str(rig["sid"]), "staff_id": rig["hk"]["id"], "duty_name": "Sweep", "duty_date": str(MON)})
    assert client.get(f"{S}/duties/sheet/staff/{rig['hk']['id']}?duty_date={MON}", headers=rig["sup"]).status_code == 403


def test_a_blank_checklist_sheet_prints_from_a_template(db, client, rig):
    r = client.get(f"{S}/checklist-templates/{rig['tpl']['id']}/sheet", headers=rig["admin"])
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and _pages(r.content) == 1
    from app.modules.staff.models.staff import ChecklistTemplate
    from app.modules.staff.services.duty_sheet_pdf import render_blank_template_sheet
    from app.utils.local_time import zone
    tpl = db.query(ChecklistTemplate).first()
    text = _text(render_blank_template_sheet(rig["society"], zone(None), tpl, compress=False))
    assert "GATE ROUND" in text and "Log visitor book" in text and "Name" in text


def test_a_long_checklist_flows_onto_more_pages_without_failing(db, client, rig):
    big = client.post(f"{S}/checklist-templates", headers=rig["admin"], json={
        "society_id": str(rig["sid"]), "department": "security", "name": "Big round",
        "items": [{"title": f"Check point {n} " + "x" * 90, "sequence": n} for n in range(60)]}).json()
    client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig["g1"]["id"]], to_date=str(MON), checklist_template_id=big["id"]))
    r = client.get(f"{S}/duties/sheet/staff/{rig['g1']['id']}?duty_date={MON}", headers=rig["admin"])
    assert r.status_code == 200 and _pages(r.content) >= 2


# ── Entering a filled-in sheet ────────────────────────────────────────────────

def _one_duty(client, rig, staff="g1"):
    client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig[staff]["id"]], to_date=str(MON), checklist_template_id=rig["tpl"]["id"]))
    return _duties(client, rig["admin"], rig[staff]["id"])[0]


def _entry(rig, duty, ticks, complete=False, staff="g1", **over):
    body = {"staff_id": rig[staff]["id"], "sheet_date": str(MON),
            "duties": [{"duty_id": duty["id"], "mark_complete": complete,
                        "items": [{"item_id": it["id"], "is_completed": ticks[i]}
                                  for i, it in enumerate(duty["checklist_items"]) if i < len(ticks)]}]}
    body.update(over)
    return body


def test_a_supervisor_enters_a_filled_in_sheet_and_it_is_marked_as_from_paper(client, rig):
    duty = _one_duty(client, rig)
    r = client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, duty, [True, True, False], complete=True))
    assert r.status_code == 200, r.text
    got = r.json()["duties"][0]
    assert got["is_completed"] and got["completion_source"] == "paper"
    items = got["checklist_items"]
    assert [i["is_completed"] for i in items] == [True, True, False]
    assert [i["entered_from_paper"] for i in items] == [True, True, True]
    assert items[0]["completed_at"] and items[2]["completed_at"] is None


def test_required_items_must_be_ticked_to_complete_and_nothing_is_half_saved(client, rig):
    duty = _one_duty(client, rig)
    r = client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, duty, [True, False, True], complete=True))
    assert r.status_code == 409 and "Log visitor book" in _why(r)
    after = _duties(client, rig["admin"], rig["g1"]["id"])[0]
    assert not after["is_completed"] and not any(i["is_completed"] for i in after["checklist_items"])
    # ticking without completing is fine: the rest can be entered later
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, duty, [True])).status_code == 200


def test_a_sheet_can_be_corrected_until_the_duty_is_verified(client, rig):
    duty = _one_duty(client, rig)
    client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, duty, [True, True, True], complete=True))
    again = client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, duty, [True, True, False]))
    assert again.status_code == 200 and again.json()["duties"][0]["checklist_items"][2]["is_completed"] is False
    client.post(f"{S}/duties/{duty['id']}/verify", json={}, headers=rig["admin"])
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"],
                       json=_entry(rig, duty, [False, True, True])).status_code == 409


def test_a_sheet_must_match_the_staff_member_and_the_day(client, rig):
    duty = _one_duty(client, rig)
    wrong_day = _entry(rig, duty, [True], sheet_date=str(MON + timedelta(days=1)))
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json=wrong_day).status_code == 422
    other_staff = _entry(rig, duty, [True], staff="g2")
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json=other_staff).status_code == 422
    bad_item = _entry(rig, duty, [True])
    bad_item["duties"][0]["items"][0]["item_id"] = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json=bad_item).status_code == 404
    future = _entry(rig, duty, [True], sheet_date=str(date.today() + timedelta(days=2)))
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json=future).status_code == 422


def test_a_supervisor_enters_sheets_only_for_their_own_department(client, rig):
    duty = _one_duty(client, rig, "hk")
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"],
                       json=_entry(rig, duty, [True], staff="hk")).status_code == 403
    assert client.post(f"{S}/sheets/entry", headers=rig["admin"],
                       json=_entry(rig, duty, [True], staff="hk")).status_code == 200


def test_the_in_and_out_times_on_the_sheet_become_approved_attendance_in_utc(client, rig):
    r = client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g1"]["id"], "sheet_date": str(MON), "check_in": "09:00", "check_out": "17:30"})
    assert r.status_code == 200, r.text
    att = r.json()["attendance"]
    # 09:00 and 17:30 India time, held and sent as UTC with a Z
    assert att["check_in_time"] == f"{MON}T03:30:00Z" and att["check_out_time"] == f"{MON}T12:00:00Z"
    assert att["working_hours"] == 8.5 and att["overtime_hours"] == 0.5 and att["status"] == "present"
    assert att["is_approved"] and att["is_checkout_approved"] and att["is_manual_entry"]
    # entering it again corrects the same day instead of adding a second record
    client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g1"]["id"], "sheet_date": str(MON), "check_in": "09:00", "check_out": "18:00"})
    daily = client.get(f"{S}/attendance/daily/{rig['sid']}?att_date={MON}", headers=rig["admin"]).json()
    assert len(daily) == 1 and daily[0]["working_hours"] == 9.0


def test_a_night_shift_sheet_ends_the_next_morning(client, rig):
    att = client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g1"]["id"], "sheet_date": str(MON), "check_in": "22:00", "check_out": "06:00"}).json()["attendance"]
    assert att["check_in_time"] == f"{MON}T16:30:00Z"
    assert att["check_out_time"] == f"{MON + timedelta(days=1)}T00:30:00Z" and att["working_hours"] == 8.0


def test_absent_sheets_and_impossible_times_are_refused_or_recorded_cleanly(client, rig):
    absent = client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g1"]["id"], "sheet_date": str(MON), "attendance_status": "absent"})
    assert absent.status_code == 200 and absent.json()["attendance"]["status"] == "absent"
    assert absent.json()["attendance"]["check_in_time"] is None
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g1"]["id"], "sheet_date": str(MON), "attendance_status": "absent",
        "check_in": "09:00"}).status_code == 422
    assert client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g2"]["id"], "sheet_date": str(MON), "check_out": "17:00"}).status_code == 422
    # 09:00 in, 08:00 out is 23 hours: a typo, not a shift
    r = client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g2"]["id"], "sheet_date": str(MON), "check_in": "09:00", "check_out": "08:00"})
    assert r.status_code == 422 and "23 hours" in _why(r)


def test_completing_in_the_app_records_who_and_that_it_was_the_app(client, db, rig):
    from tests.conftest import link_staff_login
    guard = make_user(db, "app-done@duty.io", role="Security Staff")
    link_staff_login(db, rig["g1"]["id"], guard)
    duty = _one_duty(client, rig)
    for it in duty["checklist_items"]:
        client.post(f"{S}/duties/{duty['id']}/checklist/{it['id']}/complete", json={"is_completed": True},
                    headers=guard["headers"])
    done = client.post(f"{S}/duties/{duty['id']}/complete", headers=guard["headers"]).json()
    assert done["completion_source"] == "app"
    assert all(i["entered_from_paper"] is False for i in done["checklist_items"])


def test_my_duties_can_be_limited_to_a_window_of_days(client, rig):
    client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(rig["sid"], [rig["g1"]["id"]]))
    days = [d["duty_date"] for d in client.get(
        f"{S}/duties/me/{rig['g1']['id']}?from_date={MON + timedelta(days=2)}&to_date={MON + timedelta(days=4)}",
        headers=rig["admin"]).json()]
    assert sorted(days) == [str(MON + timedelta(days=n)) for n in (2, 3, 4)]
    assert len(_duties(client, rig["admin"], rig["g1"]["id"])) == 7


# ── Cancelling ────────────────────────────────────────────────────────────────

def test_a_duty_nobody_has_started_can_be_cancelled_and_leaves_every_list(client, rig):
    duty = _one_duty(client, rig)
    r = client.post(f"{S}/duties/{duty['id']}/cancel", headers=rig["admin"])
    assert r.status_code == 200 and r.json() == {"cancelled": 1, "kept": 0}
    assert _duties(client, rig["admin"], rig["g1"]["id"]) == []
    assert client.get(f"{S}/duties/society/{rig['sid']}?duty_date={MON}", headers=rig["admin"]).json() == []
    assert client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={MON}", headers=rig["admin"]).status_code == 404
    assert client.post(f"{S}/duties/{duty['id']}/cancel", headers=rig["admin"]).status_code == 404


def test_a_duty_with_work_recorded_cannot_be_cancelled(client, rig):
    done = _one_duty(client, rig)
    client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, done, [True, True, True], complete=True))
    assert client.post(f"{S}/duties/{done['id']}/cancel", headers=rig["admin"]).status_code == 409
    other = _one_duty(client, rig, "g2")
    client.post(f"{S}/sheets/entry", headers=rig["sup"], json=_entry(rig, other, [True], staff="g2"))
    r = client.post(f"{S}/duties/{other['id']}/cancel", headers=rig["admin"])
    assert r.status_code == 409 and "work recorded" in _why(r)


def test_a_supervisor_cancels_only_their_own_departments_duties(client, rig):
    duty = _one_duty(client, rig, "hk")
    assert client.post(f"{S}/duties/{duty['id']}/cancel", headers=rig["sup"]).status_code == 403
    assert client.post(f"{S}/duties/{duty['id']}/cancel", headers=rig["admin"]).status_code == 200


def test_the_rest_of_a_plan_can_be_cancelled_from_a_day(client, rig):
    out = client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig["g1"]["id"], rig["g2"]["id"]], checklist_template_id=rig["tpl"]["id"])).json()
    # Wednesday's round for Guard One is done
    wed = [d for d in _duties(client, rig["admin"], rig["g1"]["id"]) if d["duty_date"] == str(MON + timedelta(days=2))][0]
    client.post(f"{S}/sheets/entry", headers=rig["sup"], json={
        "staff_id": rig["g1"]["id"], "sheet_date": str(MON + timedelta(days=2)),
        "duties": [{"duty_id": wed["id"], "mark_complete": False,
                    "items": [{"item_id": wed["checklist_items"][0]["id"], "is_completed": True}]}]})
    r = client.post(f"{S}/duties/series/{out['series_id']}/cancel?from_date={MON + timedelta(days=2)}",
                    headers=rig["admin"])
    # Wed-Sun for two guards = 10 duties; Guard One's Wednesday has work on it
    assert r.status_code == 200 and r.json() == {"cancelled": 9, "kept": 1}
    left = sorted(d["duty_date"] for d in _duties(client, rig["admin"], rig["g1"]["id"]))
    assert left == [str(MON), str(MON + timedelta(days=1)), str(MON + timedelta(days=2))]
    assert len(_duties(client, rig["admin"], rig["g2"]["id"])) == 2


def test_cancelling_a_plan_is_held_to_the_supervisors_department_and_society(client, db, rig):
    out = client.post(f"{S}/duties/plan", headers=rig["committee"], json=_plan(
        rig["sid"], [rig["g1"]["id"], rig["hk"]["id"]], to_date=str(MON))).json()
    r = client.post(f"{S}/duties/series/{out['series_id']}/cancel?from_date={MON}", headers=rig["sup"])
    assert r.status_code == 200 and r.json() == {"cancelled": 1, "kept": 1}      # the cleaner's duty is not theirs
    assert len(_duties(client, rig["admin"], rig["hk"]["id"])) == 1
    assert client.post(f"{S}/duties/series/00000000-0000-0000-0000-000000000000/cancel",
                       headers=rig["admin"]).status_code == 404


def test_a_plan_can_be_cancelled_for_one_staff_member_only(client, rig):
    out = client.post(f"{S}/duties/plan", headers=rig["admin"], json=_plan(
        rig["sid"], [rig["g1"]["id"], rig["g2"]["id"]])).json()
    r = client.post(f"{S}/duties/series/{out['series_id']}/cancel?from_date={MON + timedelta(days=3)}"
                    f"&staff_id={rig['g2']['id']}", headers=rig["admin"])
    assert r.status_code == 200 and r.json() == {"cancelled": 4, "kept": 0}       # Thu-Sun for Guard Two
    assert len(_duties(client, rig["admin"], rig["g1"]["id"])) == 7
    assert len(_duties(client, rig["admin"], rig["g2"]["id"])) == 3
