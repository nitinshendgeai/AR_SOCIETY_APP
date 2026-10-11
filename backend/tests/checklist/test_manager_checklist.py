"""The manager's daily checklist: what shows depends on the society's assets and staff and its state; ticks, due
dates, statutory items, live attention items, sign-off, permissions and society scoping."""
from datetime import date, datetime, timedelta

from app.models.society import Society
from app.modules.checklist.models.checklist import ChecklistItem, ChecklistLog
from app.modules.checklist.services.checklist_service import locate, schedule_text
from app.modules.inventory.models.inventory import Asset, AssetAMC, AssetCategory, AssetStatus
from app.modules.staff.models.staff import DutyAssignment, Staff, StaffDepartment, StaffStatus
from app.utils.local_time import local_today, zone
from tests.conftest import make_society, make_user

API = "/api/v1/manager-checklist"


def _member(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who


def _rig(db, tag, state="Maharashtra"):
    society = make_society(db, f"Checklist Society {tag}")
    society.state = state
    db.commit()
    return society, _member(db, f"mgr@chk{tag}.test", "Manager", society)


def _today(client, who, society):
    r = client.get(f"{API}/society/{society.id}/today", headers=who["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def _codes(data):
    return {i["code"] for i in data["items"]}


def _item(client, who, society, code):
    rows = client.get(f"{API}/society/{society.id}/items", headers=who["headers"]).json()["items"]
    return next(i for i in rows if i["code"] == code)


def _asset(db, society, category, **over):
    a = Asset(society_id=society.id, asset_code=f"AST-{category.value}-{over.pop('n', 1)}", name=f"Test {category.value}",
              asset_category=category, **over)
    db.add(a)
    db.commit()
    return a


def _staff(db, society, name, dept, n):
    s = Staff(society_id=society.id, employee_code=f"E{society.id.hex[:4]}{n}", full_name=name, mobile=f"98{n:08d}",
              department=dept, status=StaffStatus.ACTIVE)
    db.add(s)
    db.commit()
    return s


def _now_today(society):
    return local_today(zone(society.timezone))


# ── What shows depends on the society ────────────────────────────────────────────────────────────────────────────

def test_a_new_society_gets_the_standard_list_once(client, db):
    society, mgr = _rig(db, "std1")
    first = _today(client, mgr, society)
    assert {"walk_round", "complaints_review", "cash_tally"} <= _codes(first)
    total = db.query(ChecklistItem).filter(ChecklistItem.society_id == society.id).count()
    assert total > 40
    _today(client, mgr, society)
    assert db.query(ChecklistItem).filter(ChecklistItem.society_id == society.id).count() == total


def test_asset_items_appear_only_where_the_society_has_the_asset(client, db):
    society, mgr = _rig(db, "assets1")
    assert not {"lift_check", "dg_check", "fire_check"} & _codes(_today(client, mgr, society))
    _asset(db, society, AssetCategory.LIFT, n=1)
    _asset(db, society, AssetCategory.LIFT, n=2)
    _asset(db, society, AssetCategory.GENERATOR)
    data = _today(client, mgr, society)
    lift = next(i for i in data["items"] if i["code"] == "lift_check")
    assert lift["applies_because"] == "2 lifts in your assets"
    assert "dg_check" in _codes(data) and "fire_check" not in _codes(data)
    # A retired asset no longer counts.
    for a in db.query(Asset).filter(Asset.society_id == society.id, Asset.asset_category == AssetCategory.GENERATOR):
        a.status = AssetStatus.RETIRED
    db.commit()
    assert "dg_check" not in _codes(_today(client, mgr, society))


def test_staff_items_appear_only_for_departments_with_staff(client, db):
    society, mgr = _rig(db, "staff1")
    base = _codes(_today(client, mgr, society))
    assert not {"gate_register", "attendance", "housekeeping_inspect"} & base
    _staff(db, society, "Ram Guard", StaffDepartment.SECURITY, 1)
    _staff(db, society, "Sita Sweeper", StaffDepartment.HOUSEKEEPING, 2)
    data = _today(client, mgr, society)
    assert {"gate_register", "guard_turnout", "attendance", "housekeeping_inspect"} <= _codes(data)
    assert "garden_upkeep" not in _codes(data)
    gate = next(i for i in data["items"] if i["code"] == "gate_register")
    assert gate["applies_because"] == "1 security staff"


def test_legal_items_follow_the_societys_state(client, db):
    mh, mgr = _rig(db, "state1", "Maharashtra")
    _asset(db, mh, AssetCategory.LIFT)
    comp = client.get(f"{API}/society/{mh.id}/compliance", headers=mgr["headers"]).json()
    titles = " ".join(i["title"] for i in comp["items"])
    assert "Annual General Meeting" in titles and "Lift licence" in titles and "TDS return" in titles
    assert comp["jurisdiction"]["state_pack_loaded"] is True

    other, mgr2 = _rig(db, "state2", "Karnataka")
    _asset(db, other, AssetCategory.LIFT)
    comp2 = client.get(f"{API}/society/{other.id}/compliance", headers=mgr2["headers"]).json()
    titles2 = " ".join(i["title"] for i in comp2["items"])
    assert "TDS return" in titles2 and "Annual General Meeting" not in titles2 and "Lift licence" not in titles2
    j = comp2["jurisdiction"]
    assert j["state_pack_loaded"] is False and "Karnataka" in j["note"] and "not built in" in j["note"]


def test_a_society_with_no_state_is_told_to_set_it(client, db):
    society, mgr = _rig(db, "state3", None)
    note = client.get(f"{API}/society/{society.id}/compliance", headers=mgr["headers"]).json()["jurisdiction"]["note"]
    assert "Society Settings" in note


# ── Ticking ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_ticking_an_item_counts_towards_the_day_and_can_be_undone(client, db):
    society, mgr = _rig(db, "tick1")
    item = _item(client, mgr, society, "walk_round")
    before = _today(client, mgr, society)["summary"]
    r = client.post(f"{API}/items/{item['id']}/complete", headers=mgr["headers"], json={"note": "Lift lobby tile loose"})
    assert r.status_code == 200, r.text
    data = _today(client, mgr, society)
    row = next(i for i in data["items"] if i["code"] == "walk_round")
    assert row["state"] == "done" and row["log"]["note"] == "Lift lobby tile loose"
    assert row["log"]["done_by"] == mgr["user"].full_name
    assert data["summary"]["done"] == before["done"] + 1 and data["summary"]["total"] == before["total"]
    r = client.delete(f"{API}/items/{item['id']}/complete", headers=mgr["headers"],
                      params={"for_date": row["log"]["for_date"]})
    assert r.status_code == 204
    assert next(i for i in _today(client, mgr, society)["items"] if i["code"] == "walk_round")["state"] == "due"


def test_skipping_needs_a_reason_and_still_counts_as_dealt_with(client, db):
    society, mgr = _rig(db, "skip1")
    item = _item(client, mgr, society, "walk_round")
    assert client.post(f"{API}/items/{item['id']}/complete", headers=mgr["headers"],
                       json={"status": "skipped"}).status_code == 400
    assert client.post(f"{API}/items/{item['id']}/complete", headers=mgr["headers"],
                       json={"status": "skipped", "note": "Heavy rain"}).status_code == 200
    data = _today(client, mgr, society)
    assert next(i for i in data["items"] if i["code"] == "walk_round")["state"] == "skipped"
    assert data["summary"]["done"] >= 1


def test_a_date_done_in_the_future_is_refused(client, db):
    society, mgr = _rig(db, "future1")
    item = _item(client, mgr, society, "walk_round")
    tomorrow = (_now_today(society) + timedelta(days=1)).isoformat()
    assert client.post(f"{API}/items/{item['id']}/complete", headers=mgr["headers"],
                       json={"done_on": tomorrow}).status_code == 400


# ── Due dates ────────────────────────────────────────────────────────────────────────────────────────────────────

def _fake(frequency, **kw):
    it = ChecklistItem(frequency=frequency, lead_days=kw.pop("lead_days", 0), statutory=kw.pop("statutory", False),
                       created_at=kw.pop("created_at", datetime(2026, 1, 1)), **kw)
    return it


def _log(item_date, valid_until=None, status="done"):
    return ChecklistLog(for_date=item_date, status=status, done_on=item_date, valid_until=valid_until)


def test_a_weekly_item_falls_due_on_its_weekday_and_is_overdue_after():
    monday = date(2026, 10, 5)
    it = _fake("weekly", due_weekday=0)
    assert locate(it, monday, []).state == "due"
    o = locate(it, date(2026, 10, 7), [])
    assert o.due_on == monday and o.state == "overdue"
    assert locate(it, date(2026, 10, 7), [_log(monday)]).state == "done"


def test_a_weekly_item_added_midweek_waits_for_its_next_day_instead_of_starting_overdue():
    it = _fake("weekly", due_weekday=0, created_at=datetime(2026, 10, 7))
    o = locate(it, date(2026, 10, 8), [])
    assert o.due_on == date(2026, 10, 12) and o.state == "ok"
    assert locate(it, date(2026, 10, 12), []).state == "due"


def test_a_monthly_item_shows_ahead_by_its_lead_days_then_falls_due_then_overdue():
    it = _fake("monthly", due_day=7, lead_days=3)
    sept = [_log(date(2026, 9, 7))]
    assert locate(it, date(2026, 10, 2), sept).state == "ok"
    soon = locate(it, date(2026, 10, 4), sept)
    assert soon.state == "soon" and soon.due_on == date(2026, 10, 7) and soon.days == 3
    assert locate(it, date(2026, 10, 7), sept).state == "due"
    late = locate(it, date(2026, 10, 10), sept)
    assert late.state == "overdue" and late.due_on == date(2026, 10, 7)
    assert locate(it, date(2026, 10, 10), [_log(date(2026, 10, 7))] + sept).due_on == date(2026, 11, 7)
    # September's was never ticked: it is still outstanding in early October.
    assert locate(it, date(2026, 10, 2), []).state == "overdue"


def test_the_last_day_of_the_month_clamps_to_short_months():
    it = _fake("monthly", due_day=31)
    assert locate(it, date(2027, 2, 20), [_log(date(2027, 1, 31))]).due_on == date(2027, 2, 28)


def test_fixed_dates_follow_their_months_and_carry_over_until_logged():
    tds = _fake("on_dates", due_day=31, due_months="7,10,1,5", lead_days=21, statutory=True)
    assert schedule_text(tds) == "Jan, May, Jul, Oct, by the last day"
    o = locate(tds, date(2026, 10, 11), [_log(date(2026, 7, 31))])
    assert o.due_on == date(2026, 10, 31) and o.state == "soon"
    assert locate(tds, date(2026, 8, 20), [_log(date(2026, 7, 31))]).state == "ok"     # next is Oct 31: far off
    miss = locate(tds, date(2026, 11, 5), [_log(date(2026, 7, 31))])
    assert miss.due_on == date(2026, 10, 31) and miss.state == "overdue"


def test_a_statutory_date_that_passed_before_the_item_existed_asks_to_confirm():
    agm = _fake("on_dates", due_day=30, due_months="9", lead_days=45, statutory=True, created_at=datetime(2026, 10, 11))
    o = locate(agm, date(2026, 10, 11), [])
    assert o.state == "unconfirmed" and o.due_on == date(2026, 9, 30)
    # A monthly statutory date is not asked about: it simply waits for the next one.
    pf = _fake("monthly", due_day=15, statutory=True, created_at=datetime(2026, 10, 11))
    assert locate(pf, date(2026, 10, 11), []).due_on == date(2026, 10, 15)
    # A routine item added after its date passed just waits for the next one.
    routine = _fake("monthly", due_day=5, created_at=datetime(2026, 10, 11))
    assert locate(routine, date(2026, 10, 11), []).due_on == date(2026, 11, 5)


def test_a_licence_is_unrecorded_until_its_end_date_is_entered():
    it = _fake("licence", lead_days=45)
    assert locate(it, date(2026, 10, 11), []).state == "unrecorded"
    ok = locate(it, date(2026, 10, 11), [_log(date(2026, 3, 1), valid_until=date(2027, 3, 1))])
    assert ok.state == "ok" and ok.days == 141
    soon = locate(it, date(2027, 2, 1), [_log(date(2026, 3, 1), valid_until=date(2027, 3, 1))])
    assert soon.state == "soon"
    assert locate(it, date(2027, 3, 2), [_log(date(2026, 3, 1), valid_until=date(2027, 3, 1))]).state == "overdue"


def test_recording_a_licence_needs_the_date_it_runs_to(client, db):
    society, mgr = _rig(db, "lic1")
    _asset(db, society, AssetCategory.LIFT)
    lift = _item(client, mgr, society, "mh_lift_licence")
    assert lift["state"] == "unrecorded"
    assert client.post(f"{API}/items/{lift['id']}/complete", headers=mgr["headers"], json={}).status_code == 400
    today = _now_today(society)
    assert client.post(f"{API}/items/{lift['id']}/complete", headers=mgr["headers"],
                       json={"valid_until": (today - timedelta(days=1)).isoformat()}).status_code == 400
    until = today + timedelta(days=200)
    r = client.post(f"{API}/items/{lift['id']}/complete", headers=mgr["headers"],
                    json={"valid_until": until.isoformat(), "reference": "LIC/2026/881"})
    assert r.status_code == 200, r.text
    row = next(i for i in client.get(f"{API}/society/{society.id}/compliance", headers=mgr["headers"]).json()["items"]
               if i["code"] == "mh_lift_licence")
    assert row["state"] == "ok" and row["valid_until"] == until.isoformat() and row["last_reference"] == "LIC/2026/881"
    assert row["days_left"] == 200


def test_dates_to_confirm_are_counted_not_listed_among_the_days_work(client, db):
    society, mgr = _rig(db, "conf1")
    data = _today(client, mgr, society)
    assert not [i for i in data["items"] if i["state"] == "unconfirmed"]
    assert data["summary"]["compliance_unconfirmed"] >= 1
    comp = client.get(f"{API}/society/{society.id}/compliance", headers=mgr["headers"]).json()
    assert comp["summary"]["unconfirmed"] == data["summary"]["compliance_unconfirmed"]


def test_the_compliance_list_puts_what_is_late_first(client, db):
    society, mgr = _rig(db, "comp1")
    comp = client.get(f"{API}/society/{society.id}/compliance", headers=mgr["headers"]).json()
    states = [i["state"] for i in comp["items"]]
    rank = {"overdue": 0, "unconfirmed": 1, "due": 2, "soon": 3, "unrecorded": 4, "ok": 5}
    assert [rank[s] for s in states] == sorted(rank[s] for s in states)
    assert comp["summary"]["total"] == len(states) and comp["summary"]["unrecorded"] >= 1


# ── Managing the list ────────────────────────────────────────────────────────────────────────────────────────────

def test_a_manager_adds_an_item_of_their_own(client, db):
    society, mgr = _rig(db, "own1")
    body = {"title": "Check the swimming pool chlorine", "category": "technical", "frequency": "weekly",
            "due_weekday": 2}
    r = client.post(f"{API}/society/{society.id}/items", headers=mgr["headers"], json=body)
    assert r.status_code == 201, r.text
    row = next(i for i in client.get(f"{API}/society/{society.id}/items", headers=mgr["headers"]).json()["items"]
               if i["id"] == r.json()["id"])
    assert row["schedule"] == "Every Wednesday" and row["is_standard"] is False
    bad = dict(body, frequency="monthly", due_weekday=None)
    assert client.post(f"{API}/society/{society.id}/items", headers=mgr["headers"], json=bad).status_code == 400
    assert client.post(f"{API}/society/{society.id}/items", headers=mgr["headers"],
                       json=dict(body, category="nonsense")).status_code == 400
    assert client.post(f"{API}/society/{society.id}/items", headers=mgr["headers"],
                       json=dict(body, frequency="on_dates", due_day=10)).status_code == 400   # months needed
    assert client.delete(f"{API}/items/{r.json()['id']}", headers=mgr["headers"]).status_code == 204


def test_a_standard_item_is_switched_off_not_deleted_and_stays_off(client, db):
    society, mgr = _rig(db, "off1")
    walk = _item(client, mgr, society, "walk_round")
    assert client.delete(f"{API}/items/{walk['id']}", headers=mgr["headers"]).status_code == 400
    assert client.patch(f"{API}/items/{walk['id']}", headers=mgr["headers"], json={"is_enabled": False}).status_code == 200
    assert "walk_round" not in _codes(_today(client, mgr, society))
    assert db.query(ChecklistItem).filter(ChecklistItem.society_id == society.id,
                                          ChecklistItem.code == "walk_round").count() == 1


def test_only_the_office_may_switch_off_a_statutory_item(client, db):
    society, mgr = _rig(db, "stat1")
    admin = _member(db, "adm@chkstat1.test", "Society Admin", society)
    agm = _item(client, mgr, society, "mh_agm")
    assert client.patch(f"{API}/items/{agm['id']}", headers=mgr["headers"], json={"is_enabled": False}).status_code == 403
    assert client.patch(f"{API}/items/{agm['id']}", headers=admin["headers"], json={"is_enabled": False}).status_code == 200


# ── Live items: read from the society's own records ──────────────────────────────────────────────────────────────

def test_assets_overdue_for_service_and_without_cover_are_flagged_and_clear_when_fixed(client, db):
    society, mgr = _rig(db, "live1")
    today = _now_today(society)
    a = _asset(db, society, AssetCategory.PUMP, next_service_due=today - timedelta(days=3))
    keys = {l["key"] for l in _today(client, mgr, society)["live"]}
    assert "assets_service_overdue" in keys
    db.add(AssetAMC(asset_id=a.id, society_id=society.id, vendor_name="Pumps Ltd", start_date=today - timedelta(days=400),
                    end_date=today - timedelta(days=10)))
    db.commit()
    live = {l["key"]: l for l in _today(client, mgr, society)["live"]}
    assert "amc_lapsed" in live and "Test pump" in live["assets_service_overdue"]["detail"]
    a.next_service_due = today + timedelta(days=60)
    db.commit()
    assert "assets_service_overdue" not in {l["key"] for l in _today(client, mgr, society)["live"]}


def test_staff_on_duty_who_have_not_checked_in_are_flagged(client, db):
    society, mgr = _rig(db, "live2")
    ram = _staff(db, society, "Ram Guard", StaffDepartment.SECURITY, 3)
    today = _now_today(society)
    db.add(DutyAssignment(society_id=society.id, staff_id=ram.id, duty_name="Gate", duty_date=today))
    db.commit()
    live = {l["key"]: l for l in _today(client, mgr, society)["live"]}
    assert live["staff_not_in"]["count"] == 1 and "Ram Guard" in live["staff_not_in"]["detail"]
    assert "staff_no_duty" not in live


def test_staff_with_no_duty_today_are_flagged_where_duties_are_planned(client, db):
    society, mgr = _rig(db, "live3")
    ram = _staff(db, society, "Ram Guard", StaffDepartment.SECURITY, 4)
    _staff(db, society, "Sita Sweeper", StaffDepartment.HOUSEKEEPING, 5)
    today = _now_today(society)
    db.add(DutyAssignment(society_id=society.id, staff_id=ram.id, duty_name="Gate", duty_date=today,
                          start_time=None))
    db.commit()
    live = {l["key"]: l for l in _today(client, mgr, society)["live"]}
    assert live["staff_no_duty"]["count"] == 1 and "Sita Sweeper" in live["staff_no_duty"]["detail"]


# ── End of day and the printed sheet ─────────────────────────────────────────────────────────────────────────────

def test_signing_off_records_the_day_and_a_second_sign_off_updates_it(client, db):
    society, mgr = _rig(db, "sign1")
    item = _item(client, mgr, society, "walk_round")
    client.post(f"{API}/items/{item['id']}/complete", headers=mgr["headers"], json={})
    r = client.post(f"{API}/society/{society.id}/signoff", headers=mgr["headers"], json={"remarks": "All quiet"})
    assert r.status_code == 200, r.text
    assert r.json()["routine_done"] >= 1 and r.json()["signed_by"] == mgr["user"].full_name
    client.post(f"{API}/society/{society.id}/signoff", headers=mgr["headers"], json={"remarks": "Lift 2 stuck at 6pm"})
    data = _today(client, mgr, society)
    assert data["signoff"]["remarks"] == "Lift 2 stuck at 6pm"
    hist = client.get(f"{API}/society/{society.id}/history", headers=mgr["headers"]).json()
    assert len(hist) == 1 and hist[0]["ticked"] >= 1 and hist[0]["signoff"]["remarks"] == "Lift 2 stuck at 6pm"


def test_the_checklist_prints_with_boxes_to_tick(client, db):
    society, mgr = _rig(db, "pdf1")
    _asset(db, society, AssetCategory.LIFT)
    r = client.get(f"{API}/society/{society.id}/today.pdf", headers=mgr["headers"])
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"


# ── Who may use it, and whose it is ──────────────────────────────────────────────────────────────────────────────

def test_a_resident_cannot_open_the_managers_checklist(client, db):
    society, _ = _rig(db, "perm1")
    res = _member(db, "res@chkperm1.test", "Resident", society)
    assert client.get(f"{API}/society/{society.id}/today", headers=res["headers"]).status_code == 403


def test_one_society_cannot_see_or_tick_anothers_checklist(client, db):
    a, mgr_a = _rig(db, "scopeA")
    b, mgr_b = _rig(db, "scopeB")
    item_b = _item(client, mgr_b, b, "walk_round")
    assert client.get(f"{API}/society/{b.id}/today", headers=mgr_a["headers"]).status_code == 403
    assert client.get(f"{API}/society/{b.id}/compliance", headers=mgr_a["headers"]).status_code == 403
    assert client.post(f"{API}/items/{item_b['id']}/complete", headers=mgr_a["headers"], json={}).status_code == 403
    assert client.patch(f"{API}/items/{item_b['id']}", headers=mgr_a["headers"], json={"is_enabled": False}).status_code == 403
    assert client.post(f"{API}/society/{b.id}/signoff", headers=mgr_a["headers"], json={}).status_code == 403
