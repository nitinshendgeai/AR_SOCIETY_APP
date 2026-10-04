"""Floor-wise housekeeping sheets: every floor of a wing is a row, the duty's checklist
items are the tick columns, and one staff member covers a whole wing on one page."""
import re
from datetime import date

import pytest

from app.models.floor import Floor
from app.models.wing import Wing
from tests.conftest import make_society, make_user
from tests.staff.test_duty_plans_and_sheets import _pages, _text

S = "/api/v1/staff"
DAY = date(2026, 9, 7)
ITEMS = ["Corridor swept", "Corridor mopped", "Dustbins emptied", "Lift cleaned", "Staircase cleaned"]


def _wing(db, society, name, floors, named=True):
    wing = Wing(society_id=society.id, name=name, total_floors=floors)
    db.add(wing)
    db.flush()
    for n in range(floors):
        db.add(Floor(wing_id=wing.id, society_id=society.id, floor_number=n,
                     floor_name=("Ground Floor" if n == 0 else f"{n}th Floor") if named else None))
    db.commit()
    return wing


@pytest.fixture
def rig(db, client):
    admin = make_user(db, "floor-admin@duty.io", role="Society Admin")
    society = make_society(db, "Tower Society")
    h = admin["headers"]
    staff = []
    for i, name in enumerate(["Sunita Pawar", "Rekha More", "Anita Shinde"]):
        r = client.post(f"{S}/", headers=h, json={"society_id": str(society.id), "full_name": name,
                                                   "mobile": f"98110000{i:02d}", "email": f"hk{i}@floor.io",
                                                   "department": "housekeeping"})
        assert r.status_code == 201, r.text
        staff.append(r.json())
    tpl = client.post(f"{S}/checklist-templates", headers=h, json={
        "society_id": str(society.id), "department": "housekeeping", "name": "Floor cleaning round",
        "items": [{"title": t, "sequence": i, "is_required": i < 2} for i, t in enumerate(ITEMS)]})
    assert tpl.status_code == 201, tpl.text
    return {"h": h, "society": society, "sid": society.id, "staff": staff, "tpl": tpl.json()}


def _assign_all(client, rig):
    r = client.post(f"{S}/duties/plan", headers=rig["h"], json={
        "society_id": str(rig["sid"]), "staff_ids": [s["id"] for s in rig["staff"]], "duty_name": "Floor cleaning",
        "from_date": str(DAY), "to_date": str(DAY), "checklist_template_id": rig["tpl"]["id"]})
    assert r.status_code == 201, r.text


def _sheet(client, rig, query="", who="society"):
    return client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={DAY}&layout=floors{query}", headers=rig["h"])


def test_three_staff_get_one_page_each_with_all_23_floors(db, client, rig):
    _wing(db, rig["society"], "Tower A", 23)
    _assign_all(client, rig)
    r = _sheet(client, rig)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert _pages(r.content) == 3                                         # one page per housekeeping staff
    from app.modules.staff.models.staff import DutyAssignment
    from app.modules.staff.services.duty_sheet_pdf import render_floor_sheets
    from app.utils.local_time import zone
    duty = db.query(DutyAssignment).filter(DutyAssignment.duty_name == "Floor cleaning").first()
    one = render_floor_sheets(rig["society"], zone("Asia/Kolkata"),
                              [{"staff": duty.staff, "date": DAY, "duties": [duty]}],
                              [{"label": "Tower A", "floors": ["Ground Floor"] + [f"{n}th Floor" for n in range(1, 23)]}],
                              compress=False)
    assert _pages(one) == 1
    text = _text(one)
    for expected in ("Ground Floor", "1th Floor", "22th Floor", "Floor", "Time", "Initials", "Tower A",
                     "Sunita Pawar", "Corridor|swept", "Lift cleaned", "Staircase|cleaned", "Supervisor signature"):
        assert expected in text, expected
    assert len(re.findall(r"\dth Floor", text)) == 22
    # the two required items carry the star, the others don't
    assert text.count("| |*") == 2 and "emptied|*" not in text


def test_each_wing_is_its_own_page_and_one_wing_can_be_asked_for(db, client, rig):
    a = _wing(db, rig["society"], "Tower A", 23)
    _wing(db, rig["society"], "Tower B", 23)
    _assign_all(client, rig)
    assert _pages(_sheet(client, rig).content) == 6                      # 3 staff x 2 wings
    assert _pages(_sheet(client, rig, f"&wing_id={a.id}").content) == 3
    assert _sheet(client, rig, "&wing_id=00000000-0000-0000-0000-000000000000").status_code == 404


def test_a_wing_of_another_society_is_not_reachable(db, client, rig):
    other = make_society(db, "Other Society")
    foreign = _wing(db, other, "Foreign", 5)
    _assign_all(client, rig)
    _wing(db, rig["society"], "Tower A", 5)
    assert _sheet(client, rig, f"&wing_id={foreign.id}").status_code == 404


def test_floors_not_entered_fall_back_to_the_wings_total(db, client, rig):
    wing = Wing(society_id=rig["sid"], name="Tower C", total_floors=23)
    db.add(wing)
    db.commit()
    _assign_all(client, rig)
    from app.modules.staff.services.staff_service import StaffService
    assert StaffService(db).floor_wings(rig["sid"]) == [
        {"label": "Tower C", "floors": [f"Floor {n}" for n in range(1, 24)]}]
    assert _sheet(client, rig).status_code == 200


def test_a_society_with_no_floors_is_told_to_add_them(client, rig):
    _assign_all(client, rig)
    r = _sheet(client, rig)
    assert r.status_code == 422 and "Add the wings and floors" in str(r.json())


def test_unnamed_floors_are_labelled_by_number(db, client, rig):
    _wing(db, rig["society"], "Tower A", 3, named=False)
    from app.modules.staff.services.staff_service import StaffService
    assert StaffService(db).floor_wings(rig["sid"])[0]["floors"] == ["Ground", "Floor 1", "Floor 2"]


def test_the_default_layout_is_still_the_plain_checklist(db, client, rig):
    _wing(db, rig["society"], "Tower A", 23)
    _assign_all(client, rig)
    plain = client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={DAY}", headers=rig["h"])
    assert plain.status_code == 200 and _pages(plain.content) == 3
    assert b"DAILY DUTY SHEET" in plain.content or plain.content.startswith(b"%PDF")
    assert client.get(f"{S}/duties/sheet/society/{rig['sid']}?duty_date={DAY}&layout=weird", headers=rig["h"]).status_code == 422


def test_a_staff_member_prints_their_floor_sheet_from_their_own_endpoint(db, client, rig):
    _wing(db, rig["society"], "Tower A", 23)
    _assign_all(client, rig)
    r = client.get(f"{S}/duties/sheet/staff/{rig['staff'][0]['id']}?duty_date={DAY}&layout=floors", headers=rig["h"])
    assert r.status_code == 200 and _pages(r.content) == 1


def test_the_blank_template_prints_as_a_floor_sheet_too(db, client, rig):
    _wing(db, rig["society"], "Tower A", 23)
    r = client.get(f"{S}/checklist-templates/{rig['tpl']['id']}/sheet?layout=floors", headers=rig["h"])
    assert r.status_code == 200 and _pages(r.content) == 1


def test_a_very_tall_wing_runs_on_to_a_second_page_with_the_headings_repeated(db, client, rig):
    _wing(db, rig["society"], "Tower A", 60)
    r = client.get(f"{S}/checklist-templates/{rig['tpl']['id']}/sheet?layout=floors", headers=rig["h"])
    assert r.status_code == 200 and _pages(r.content) == 2
