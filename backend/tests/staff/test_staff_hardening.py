"""Staff: what the forms send is checked; nothing crosses a society; people act
only on their own duties/attendance/handovers; a missing roster or staff reads as
404, not a crash."""
import pytest
from datetime import date, timedelta
from uuid import UUID as _UUID

from tests.conftest import make_user, make_society, link_staff_login

S = "/api/v1/staff"


def _in(db, user, society):
    user["user"].society_id = _UUID(str(society.id))
    db.commit()
    return user


@pytest.fixture
def rig(db):
    society = make_society(db, "Staff Hardening Society")
    other = make_society(db, "Other Staff Society")
    admin = _in(db, make_user(db, "shadm@s.com", role="Society Admin"), society)
    mgr = _in(db, make_user(db, "shmgr@s.com", role="Manager"), society)
    oadmin = _in(db, make_user(db, "shoadm@s.com", role="Society Admin"), other)
    return dict(society=society, other=other, admin=admin, mgr=mgr, oadmin=oadmin, h=admin["headers"])


def _staff(client, rig, who="admin", **kw):
    body = {"society_id": str(rig["society"].id), "full_name": "Ravi Kumar", "mobile": "9876500101",
            "department": "security", **kw}
    return client.post(f"{S}/", json=body, headers=rig[who]["headers"])


def test_staff_fields_are_checked_and_tidied(client, rig):
    assert _staff(client, rig, full_name="  ").status_code == 422
    assert _staff(client, rig, full_name="n" * 256).status_code == 422
    assert _staff(client, rig, mobile="12345").status_code == 422
    assert _staff(client, rig, email="nope").status_code == 422
    assert _staff(client, rig, base_salary=-5).status_code == 422
    assert _staff(client, rig, joining_date="0001-01-01").status_code == 422
    assert _staff(client, rig, emergency_contact_phone="abc").status_code == 422
    assert _staff(client, rig, address="a" * 1001).status_code == 422
    r = _staff(client, rig, full_name=" Ravi   Kumar ", email=" Ravi@Example.COM ", address="  ")
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["full_name"] == "Ravi Kumar" and j["email"] == "ravi@example.com" and j["address"] is None
    assert j["temp_password"]


def test_duplicate_mobile_and_login_email_are_refused(client, rig):
    assert _staff(client, rig, email="dup1@example.com").status_code == 201
    r = _staff(client, rig, full_name="Someone Else", email="dup2@example.com")
    assert r.status_code == 409 and "mobile" in r.json()["detail"].lower()
    r = _staff(client, rig, full_name="Someone Else", mobile="9876500102", email="DUP1@example.com")
    assert r.status_code == 409 and "email" in r.json()["detail"].lower()


def test_employee_codes_never_repeat(client, rig):
    codes = [_staff(client, rig, mobile=f"98765001{i:02d}").json()["employee_code"] for i in range(3)]
    assert len(set(codes)) == 3


def test_staff_never_cross_a_society(client, rig):
    sid = _staff(client, rig).json()["id"]
    oh = rig["oadmin"]["headers"]
    assert client.get(f"{S}/{sid}", headers=oh).status_code == 404
    assert client.patch(f"{S}/{sid}", json={"full_name": "X"}, headers=oh).status_code == 404
    assert client.get(f"{S}/society/{rig['society'].id}", headers=oh).status_code == 403
    assert client.get(f"{S}/designations/{rig['society'].id}", headers=oh).status_code == 403
    assert client.get(f"{S}/shifts/{rig['society'].id}", headers=oh).status_code == 403
    assert client.get(f"{S}/duties/society/{rig['society'].id}?duty_date={date.today()}", headers=oh).status_code == 403
    assert client.get(f"{S}/attendance/daily/{rig['society'].id}?att_date={date.today()}", headers=oh).status_code == 403
    assert client.get(f"{S}/leaves/pending/{rig['society'].id}", headers=oh).status_code == 403
    assert client.get(f"{S}/roster/society/{rig['society'].id}", headers=oh).status_code == 403
    # Creating in, or linking to, another society
    assert _staff(client, rig, who="oadmin").status_code == 403
    d = client.post(f"{S}/designations", json={"society_id": str(rig["other"].id), "name": "Guard",
                                               "department": "security"}, headers=rig["h"])
    assert d.status_code == 403
    od = client.post(f"{S}/designations", json={"society_id": str(rig["other"].id), "name": "Guard",
                                                "department": "security"}, headers=oh).json()
    assert _staff(client, rig, mobile="9876500103", designation_id=od["id"]).status_code == 422


def test_staff_update_clears_optional_fields_but_not_required_ones(client, rig):
    sid = _staff(client, rig, email="clr@example.com", address="Somewhere",
                 emergency_contact_name="Raj", emergency_contact_phone="9876500111").json()["id"]
    p = client.patch(f"{S}/{sid}", json={"address": None, "emergency_contact_name": None,
                                         "emergency_contact_phone": None, "full_name": None, "mobile": None},
                     headers=rig["h"])
    assert p.status_code == 200, p.text
    j = p.json()
    assert j["address"] is None and j["emergency_contact_name"] is None and j["emergency_contact_phone"] is None
    assert j["full_name"] == "Ravi Kumar" and j["mobile"] == "9876500101"
    other = _staff(client, rig, mobile="9876500122", full_name="Second").json()["id"]
    assert client.patch(f"{S}/{other}", json={"mobile": "9876500101"}, headers=rig["h"]).status_code == 409
    assert client.patch(f"{S}/{sid}", json={"base_salary": -1}, headers=rig["h"]).status_code == 422


def test_designations_shifts_and_templates_are_checked(client, rig):
    sid = str(rig["society"].id)
    h = rig["h"]
    assert client.post(f"{S}/designations", json={"society_id": sid, "name": " ", "department": "security"}, headers=h).status_code == 422
    g = client.post(f"{S}/designations", json={"society_id": sid, "name": " Head  Guard ", "department": "security"}, headers=h)
    assert g.status_code == 201 and g.json()["name"] == "Head Guard"
    assert client.post(f"{S}/designations", json={"society_id": sid, "name": "head guard", "department": "security"}, headers=h).status_code == 409
    assert client.post(f"{S}/shifts", json={"society_id": sid, "name": "Night", "start_time": "22:00", "end_time": "06:00"},
                       headers=h).status_code == 422
    assert client.post(f"{S}/shifts", json={"society_id": sid, "name": "Night", "start_time": "22:00", "end_time": "06:00",
                                            "is_overnight": True}, headers=h).status_code == 201
    assert client.post(f"{S}/shifts", json={"society_id": sid, "name": "night", "start_time": "22:00", "end_time": "06:00",
                                            "is_overnight": True}, headers=h).status_code == 409
    tpl = {"society_id": sid, "department": "security", "name": "Gate Round", "items": [{"title": "Lock gate"}]}
    assert client.post(f"{S}/checklist-templates", json={**tpl, "name": " "}, headers=h).status_code == 422
    assert client.post(f"{S}/checklist-templates", json={**tpl, "items": [{"title": " "}]}, headers=h).status_code == 422
    t = client.post(f"{S}/checklist-templates", json=tpl, headers=h)
    assert t.status_code == 201
    assert client.post(f"{S}/checklist-templates", json=tpl, headers=h).status_code == 409
    assert client.get(f"{S}/checklist-templates/{t.json()['id']}", headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.delete(f"{S}/checklist-templates/{t.json()['id']}", headers=rig["oadmin"]["headers"]).status_code == 404


def test_duties_belong_to_the_staff_member_and_their_society(client, db, rig):
    sid = _staff(client, rig).json()["id"]
    login = make_user(db, "shguard@s.com", role="Security Staff")
    _in(db, login, rig["society"])
    link_staff_login(db, sid, login)
    stranger = _in(db, make_user(db, "shstranger@s.com", role="Security Staff"), rig["society"])
    h = rig["h"]
    body = {"society_id": str(rig["society"].id), "staff_id": sid, "duty_name": "  Gate  Round ", "duty_date": str(date.today())}
    assert client.post(f"{S}/duties", json={**body, "duty_name": " "}, headers=h).status_code == 422
    d = client.post(f"{S}/duties", json=body, headers=h)
    assert d.status_code == 201 and d.json()["duty_name"] == "Gate Round"
    did = d.json()["id"]
    # Another society's admin can't assign to this staff member
    assert client.post(f"{S}/duties", json={**body, "society_id": str(rig["other"].id)},
                       headers=rig["oadmin"]["headers"]).status_code == 404
    # A colleague can't complete it or read its checklist; the member can
    assert client.post(f"{S}/duties/{did}/complete", headers=stranger["headers"]).status_code == 403
    assert client.get(f"{S}/duties/me/{sid}", headers=stranger["headers"]).status_code == 403
    assert client.post(f"{S}/duties/{did}/complete", headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.post(f"{S}/duties/{did}/complete", headers=login["headers"]).status_code == 200


def test_attendance_manual_entry_is_checked(client, rig):
    sid = _staff(client, rig).json()["id"]
    h = rig["h"]
    body = {"society_id": str(rig["society"].id), "staff_id": sid, "attendance_date": str(date.today()),
            "status": "present"}
    assert client.post(f"{S}/attendance/manual", json={**body, "attendance_date": str(date.today() + timedelta(days=3))},
                       headers=h).status_code == 422
    assert client.post(f"{S}/attendance/manual", json={**body, "check_in_time": "2026-01-01T10:00:00",
                                                       "check_out_time": "2026-01-01T09:00:00"}, headers=h).status_code == 422
    assert client.post(f"{S}/attendance/manual", json=body, headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.post(f"{S}/attendance/manual", json=body, headers=h).status_code == 200


def test_leaves_and_rosters_are_checked_and_never_crash(client, rig):
    sid = _staff(client, rig).json()["id"]
    h = rig["h"]
    sc = str(rig["society"].id)
    today = date.today()
    assert client.post(f"{S}/leaves/{sid}", json={"society_id": sc, "leave_type": "casual", "from_date": str(today),
                                                  "to_date": str(today - timedelta(days=1))}, headers=h).status_code == 422
    assert client.post(f"{S}/leaves/{sid}", json={"society_id": sc, "leave_type": "casual", "from_date": str(today),
                                                  "to_date": str(today + timedelta(days=400))}, headers=h).status_code == 422
    lv = client.post(f"{S}/leaves/{sid}", json={"society_id": sc, "leave_type": "casual", "from_date": str(today),
                                                "to_date": str(today + timedelta(days=1)), "reason": " Family "}, headers=h)
    assert lv.status_code == 201, lv.text
    lid = lv.json()["id"]
    assert client.post(f"{S}/leaves/{lid}/reject", json={"reason": "  "}, headers=h).status_code == 422
    assert client.post(f"{S}/leaves/{lid}/approve", json={}, headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.post(f"{S}/leaves/{lid}/approve", json={}, headers=h).status_code == 200
    # A roster that doesn't exist, or a staff member that doesn't, is a 404 (it used to be a crash)
    assert client.patch(f"{S}/roster/00000000-0000-0000-0000-000000000009/publish", headers=h).status_code == 404
    assert client.get(f"{S}/leave-balance/00000000-0000-0000-0000-000000000009/2026", headers=h).status_code == 404
    assert client.get(f"{S}/leave-balance/{sid}/2026", headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.get(f"{S}/leave-balance/{sid}/2026", headers=h).status_code == 200
    week = {"society_id": sc, "staff_id": sid, "week_start": str(today), "week_end": str(today + timedelta(days=6))}
    assert client.post(f"{S}/roster", json={**week, "week_end": str(today + timedelta(days=20))}, headers=h).status_code == 422
    r = client.post(f"{S}/roster", json=week, headers=h)
    assert r.status_code == 201
    assert client.patch(f"{S}/roster/{r.json()['id']}/publish", headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.patch(f"{S}/roster/{r.json()['id']}/publish", headers=h).status_code == 200


def test_handovers_are_scoped_and_only_the_parties_act(client, db, rig):
    out = _staff(client, rig, mobile="9876500201", full_name="Outgoing").json()["id"]
    inc = _staff(client, rig, mobile="9876500202", full_name="Incoming").json()["id"]
    out_login = _in(db, make_user(db, "shout@s.com", role="Security Staff"), rig["society"])
    inc_login = _in(db, make_user(db, "shinc@s.com", role="Security Staff"), rig["society"])
    other_login = _in(db, make_user(db, "shoth@s.com", role="Security Staff"), rig["society"])
    link_staff_login(db, out, out_login)
    link_staff_login(db, inc, inc_login)
    H = "/api/v1/handovers"
    body = {"society_id": str(rig["society"].id), "outgoing_staff_id": out, "incoming_staff_id": inc,
            "summary": " All quiet ", "items": [{"item_type": "key", "title": "Gate key"}]}
    assert client.post(f"{H}/", json={**body, "summary": " "}, headers=out_login["headers"]).status_code == 422
    assert client.post(f"{H}/", json={**body, "incoming_staff_id": out}, headers=out_login["headers"]).status_code == 422
    assert client.post(f"{H}/", json={**body, "shift_start": "2026-01-01T10:00:00", "shift_end": "2026-01-01T09:00:00"},
                       headers=out_login["headers"]).status_code == 422
    assert client.post(f"{H}/", json=body, headers=rig["oadmin"]["headers"]).status_code == 403
    hv = client.post(f"{H}/", json=body, headers=out_login["headers"])
    assert hv.status_code == 201, hv.text
    hid = hv.json()["id"]
    assert client.get(f"{H}/{hid}", headers=rig["oadmin"]["headers"]).status_code == 404
    assert client.post(f"{H}/{hid}/submit", headers=other_login["headers"]).status_code == 403
    assert client.post(f"{H}/{hid}/submit", headers=out_login["headers"]).status_code == 200
    assert client.post(f"{H}/{hid}/accept", json={}, headers=other_login["headers"]).status_code == 403
    assert client.post(f"{H}/{hid}/accept", json={}, headers=inc_login["headers"]).status_code == 200
    assert client.get(f"{H}/pending/{inc}", headers=other_login["headers"]).status_code == 403
    assert client.get(f"{H}/society/{rig['society'].id}", headers=rig["oadmin"]["headers"]).status_code == 403
    assert client.get(f"{H}/society/{rig['society'].id}?limit=100000", headers=rig["admin"]["headers"]).status_code == 422


def test_complaint_department_assignment_is_scoped(client, db, rig):
    from tests.conftest import make_user as mk
    resident = _in(db, mk(db, "shres@s.com", role="Resident"), rig["society"])
    c = client.post("/api/v1/complaints/", json={"title": "Leak", "description": "Leak in the lobby", "category": "plumbing",
                                                 "society_id": str(rig["society"].id)}, headers=rig["admin"]["headers"])
    assert c.status_code == 201, c.text
    cid = c.json()["id"]
    r = client.post(f"{S}/complaints/assign-department", json={"complaint_id": cid, "department": "technical"},
                    headers=rig["oadmin"]["headers"])
    assert r.status_code == 404
    r = client.post(f"{S}/complaints/assign-department", json={"complaint_id": cid, "department": "technical"},
                    headers=rig["mgr"]["headers"])
    assert r.status_code == 200
