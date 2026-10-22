"""Ready-made daily checklists for plumber, electrician and a single person doing both.

A manager adds them to the society's templates; they are then the society's own: assignable to a duty (which
snapshots the items), printable on one page, and never added twice.
"""
import re
from datetime import date

import pytest

from app.modules.staff.services.standard_checklists import BY_CODE, STANDARD_CHECKLISTS
from tests.conftest import make_society, make_user, place_in

S = "/api/v1/staff"
STD = f"{S}/checklist-templates/standard"
MON = date(2026, 9, 7)


@pytest.fixture
def rig(db, client):
    admin = make_user(db, "std-admin@chk.io", role="Society Admin")
    society = make_society(db, "Standard Society")
    return {"admin": admin["headers"], "db": db, "sid": str(society.id), "society": society}


def test_catalog_lists_the_three_rounds_with_their_departments(client, rig):
    r = client.get(f"{STD}/{rig['sid']}", headers=rig["admin"])
    assert r.status_code == 200, r.text
    by = {c["code"]: c for c in r.json()}
    assert set(by) == {"plumber_daily", "electrician_daily", "plumber_electrician_daily"}
    assert by["plumber_daily"]["department"] == "plumbing"
    assert by["electrician_daily"]["department"] == "electrical"
    assert by["plumber_electrician_daily"]["department"] == "maintenance"
    assert all(c["already_added"] is False and c["required_count"] > 0 for c in by.values())
    assert by["plumber_electrician_daily"]["item_count"] == 12


def test_adding_creates_templates_with_items_and_marks_them_added(client, rig):
    r = client.post(f"{STD}/{rig['sid']}", headers=rig["admin"], json={"codes": ["plumber_daily", "electrician_daily"]})
    assert r.status_code == 201, r.text
    out = {t["name"]: t for t in r.json()}
    assert set(out) == {"Plumber: daily round", "Electrician: daily round"}
    plumber = out["Plumber: daily round"]
    assert plumber["department"] == "plumbing" and len(plumber["items"]) == 12
    assert [i["sequence"] for i in plumber["items"]] == list(range(12))
    assert any(not i["is_required"] for i in plumber["items"])
    listed = client.get(f"{STD}/{rig['sid']}", headers=rig["admin"]).json()
    assert {c["code"]: c["already_added"] for c in listed} == {
        "plumber_daily": True, "electrician_daily": True, "plumber_electrician_daily": False}


def test_adding_twice_skips_what_the_society_already_has(client, rig):
    first = client.post(f"{STD}/{rig['sid']}", headers=rig["admin"], json={"codes": ["plumber_daily"]})
    assert len(first.json()) == 1
    again = client.post(f"{STD}/{rig['sid']}", headers=rig["admin"],
                        json={"codes": ["plumber_daily", "plumber_daily", "plumber_electrician_daily"]})
    assert [t["name"] for t in again.json()] == ["Plumber and electrician: daily round"]
    all_t = client.get(f"{S}/checklist-templates/society/{rig['sid']}", headers=rig["admin"]).json()
    assert len(all_t) == 2


def test_unknown_code_and_empty_list_are_refused(client, rig):
    assert client.post(f"{STD}/{rig['sid']}", headers=rig["admin"], json={"codes": ["nope"]}).status_code == 422
    assert client.post(f"{STD}/{rig['sid']}", headers=rig["admin"], json={"codes": []}).status_code == 422
    assert client.get(f"{S}/checklist-templates/society/{rig['sid']}", headers=rig["admin"]).json() == []


def test_only_a_manager_or_above_can_add_and_only_for_their_society(client, db, rig):
    resident = place_in(db, make_user(db, "std-res@chk.io", role="Resident"), rig["society"])
    assert client.get(f"{STD}/{rig['sid']}", headers=resident["headers"]).status_code == 403
    assert client.post(f"{STD}/{rig['sid']}", headers=resident["headers"],
                       json={"codes": ["plumber_daily"]}).status_code == 403
    other = make_society(db, "Other Society")
    mgr = place_in(db, make_user(db, "std-mgr@chk.io", role="Manager"), other)
    assert client.post(f"{STD}/{rig['sid']}", headers=mgr["headers"], json={"codes": ["plumber_daily"]}).status_code in (403, 404)
    assert client.post(f"{STD}/{str(other.id)}", headers=mgr["headers"], json={"codes": ["plumber_daily"]}).status_code == 201


def test_a_duty_plan_with_a_standard_round_blocks_completion_until_required_lines_are_ticked(client, rig):
    h = rig["admin"]
    tpl = client.post(f"{STD}/{rig['sid']}", headers=h, json={"codes": ["plumber_electrician_daily"]}).json()[0]
    staff = client.post(f"{S}/", headers=h, json={
        "society_id": rig["sid"], "full_name": "Raju Handyman", "mobile": "9833000001",
        "email": "raju@chk.io", "department": "maintenance", "role": "Technical Staff"})
    assert staff.status_code == 201, staff.text
    staff = staff.json()
    plan = client.post(f"{S}/duties/plan", headers=h, json={
        "society_id": rig["sid"], "staff_ids": [staff["id"]], "duty_name": "Daily round",
        "from_date": str(MON), "to_date": str(MON), "checklist_template_id": tpl["id"]})
    assert plan.status_code == 201, plan.text
    assert plan.json()["created"] == 1
    duty = client.get(f"{S}/duties/me/{staff['id']}", headers=h).json()[0]
    items = duty["checklist_items"]
    assert len(items) == 12 and sum(1 for i in items if i["is_required"]) == 11
    blocked = client.post(f"{S}/duties/{duty['id']}/complete", headers=h, json={})
    assert blocked.status_code in (400, 409, 422), blocked.text


def test_each_round_prints_on_one_page(client, rig):
    h = rig["admin"]
    made = client.post(f"{STD}/{rig['sid']}", headers=h, json={"codes": [c["code"] for c in STANDARD_CHECKLISTS]}).json()
    assert len(made) == 3
    for t in made:
        r = client.get(f"{S}/checklist-templates/{t['id']}/sheet", headers=h)
        assert r.status_code == 200, r.text
        assert r.content.startswith(b"%PDF")
        pages = len(re.findall(rb"/Type\s*/Page\b", r.content))
        assert pages == 1, f"{t['name']} prints on {pages} pages"


def test_catalog_is_well_formed():
    for c in STANDARD_CHECKLISTS:
        assert BY_CODE[c["code"]] is c
        titles = [t for t, _, _ in c["items"]]
        assert len(titles) == len(set(titles)) and all(len(t) <= 255 for t in titles)
        assert any(r for _, _, r in c["items"])


# ── Printing a standard round in Hindi or English ────────────────────────────

def _pages(content: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", content))


def test_every_standard_round_prints_in_hindi_on_one_page(client, rig):
    for c in STANDARD_CHECKLISTS:
        r = client.get(f"{STD}/{rig['sid']}/{c['code']}/sheet", headers=rig["admin"])
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
        assert _pages(r.content) == 1, f"{c['code']} prints on {_pages(r.content)} pages"


def test_english_sheet_is_available_for_a_standard_round_before_it_is_added(client, rig):
    r = client.get(f"{STD}/{rig['sid']}/plumber_daily/sheet?lang=en", headers=rig["admin"])
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and _pages(r.content) == 1
    listed = client.get(f"{STD}/{rig['sid']}", headers=rig["admin"]).json()
    assert all(c["already_added"] is False for c in listed)  # printing does not add it


def test_sheet_refuses_unknown_round_bad_language_and_non_managers(client, db, rig):
    assert client.get(f"{STD}/{rig['sid']}/nope/sheet", headers=rig["admin"]).status_code == 404
    assert client.get(f"{STD}/{rig['sid']}/plumber_daily/sheet?lang=fr", headers=rig["admin"]).status_code == 422
    resident = place_in(db, make_user(db, "std-res2@chk.io", role="Resident"), rig["society"])
    assert client.get(f"{STD}/{rig['sid']}/plumber_daily/sheet", headers=resident["headers"]).status_code == 403


def test_hindi_text_matches_the_english_rounds_line_for_line():
    from app.modules.staff.services.standard_checklists_hi import HINDI
    assert set(HINDI) == set(BY_CODE)
    for code, c in BY_CODE.items():
        hi = HINDI[code]
        assert len(hi["items"]) == len(c["items"]), code
        assert all(title.strip() and note.strip() for title, note in hi["items"])
        assert hi["name"].strip() and hi["description"].strip()
