"""
Checklist templates — department-scoped, reusable staff duty checklists.

Admin/Committee define a named checklist (e.g. "Security Gate Round") with
ordered items; assigning a duty from a template snapshots the items onto
the duty so later template edits don't retroactively change an
already-assigned checklist. A duty with required checklist items cannot be
marked complete until all required items are checked off.
"""
import pytest
from datetime import date
from tests.conftest import make_user, make_society


def _template_payload(society_id, department="security", name="Gate Round"):
    return {
        "society_id": str(society_id),
        "department": department,
        "name": name,
        "description": "Standard patrol checklist",
        "items": [
            {"title": "Check main gate lock", "sequence": 0, "is_required": True},
            {"title": "Log visitor book", "sequence": 1, "is_required": True},
            {"title": "Inspect CCTV feed", "sequence": 2, "is_required": False},
        ],
    }


def _create_staff(client, headers, society_id, full_name, mobile, email, dept):
    r = client.post(
        "/api/v1/staff/",
        json={"society_id": str(society_id), "full_name": full_name,
              "mobile": mobile, "email": email, "department": dept},
        headers=headers,
    )
    assert r.status_code == 201, f"create_staff failed: {r.text}"
    return r.json()


@pytest.fixture
def rig(db, client):
    admin = make_user(db, "chk-admin@stf.com", role="Society Admin")
    society = make_society(db, "Checklist Society")
    guard = _create_staff(client, admin["headers"], society.id,
                          "Checklist Guard", "9822000001", "chkguard@stf.io", "security")
    return {"admin": admin, "society": society, "guard": guard}


# ── Template CRUD ────────────────────────────────────────────────────────────

def test_admin_can_create_template_with_items(client, db, rig):
    r = client.post("/api/v1/staff/checklist-templates",
                    json=_template_payload(rig["society"].id),
                    headers=rig["admin"]["headers"])
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Gate Round"
    assert data["department"] == "security"
    assert len(data["items"]) == 3
    assert data["items"][0]["title"] == "Check main gate lock"


def test_resident_cannot_create_template(client, db, rig):
    resident = make_user(db, "chk-res1@stf.com", role="Resident")
    r = client.post("/api/v1/staff/checklist-templates",
                    json=_template_payload(rig["society"].id),
                    headers=resident["headers"])
    assert r.status_code == 403


def test_list_templates_filtered_by_department(client, db, rig):
    client.post("/api/v1/staff/checklist-templates",
               json=_template_payload(rig["society"].id, "security", "Gate Round"),
               headers=rig["admin"]["headers"])
    client.post("/api/v1/staff/checklist-templates",
               json=_template_payload(rig["society"].id, "housekeeping", "Room Turnover"),
               headers=rig["admin"]["headers"])

    r = client.get(f"/api/v1/staff/checklist-templates/society/{rig['society'].id}?department=security",
                   headers=rig["admin"]["headers"])
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert "Gate Round" in names
    assert "Room Turnover" not in names


def test_update_template_replaces_items(client, db, rig):
    create = client.post("/api/v1/staff/checklist-templates",
                         json=_template_payload(rig["society"].id),
                         headers=rig["admin"]["headers"])
    tid = create.json()["id"]

    r = client.patch(f"/api/v1/staff/checklist-templates/{tid}",
                     json={"items": [{"title": "New single item", "sequence": 0, "is_required": True}]},
                     headers=rig["admin"]["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "New single item"


def test_delete_template_soft_deletes(client, db, rig):
    create = client.post("/api/v1/staff/checklist-templates",
                         json=_template_payload(rig["society"].id),
                         headers=rig["admin"]["headers"])
    tid = create.json()["id"]

    r = client.delete(f"/api/v1/staff/checklist-templates/{tid}",
                      headers=rig["admin"]["headers"])
    assert r.status_code == 204

    listing = client.get(f"/api/v1/staff/checklist-templates/society/{rig['society'].id}",
                         headers=rig["admin"]["headers"])
    assert all(t["id"] != tid for t in listing.json())


# ── Duty from template ───────────────────────────────────────────────────────

def test_assign_duty_from_template_snapshots_items(client, db, rig):
    template = client.post("/api/v1/staff/checklist-templates",
                           json=_template_payload(rig["society"].id),
                           headers=rig["admin"]["headers"]).json()

    duty = client.post("/api/v1/staff/duties",
                       json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                             "duty_name": "Gate Round", "duty_date": str(date.today()),
                             "checklist_template_id": template["id"]},
                       headers=rig["admin"]["headers"])
    assert duty.status_code == 201, duty.text
    data = duty.json()
    assert data["checklist_template_id"] == template["id"]
    assert len(data["checklist_items"]) == 3
    assert {i["title"] for i in data["checklist_items"]} == {
        "Check main gate lock", "Log visitor book", "Inspect CCTV feed"}
    assert all(not i["is_completed"] for i in data["checklist_items"])


def test_template_edit_does_not_change_already_assigned_duty(client, db, rig):
    template = client.post("/api/v1/staff/checklist-templates",
                           json=_template_payload(rig["society"].id),
                           headers=rig["admin"]["headers"]).json()

    duty = client.post("/api/v1/staff/duties",
                       json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                             "duty_name": "Gate Round", "duty_date": str(date.today()),
                             "checklist_template_id": template["id"]},
                       headers=rig["admin"]["headers"]).json()

    # Now change the template to a single different item.
    client.patch(f"/api/v1/staff/checklist-templates/{template['id']}",
                json={"items": [{"title": "Totally different item", "sequence": 0}]},
                headers=rig["admin"]["headers"])

    checklist = client.get(f"/api/v1/staff/duties/{duty['id']}/checklist",
                           headers=rig["admin"]["headers"])
    assert checklist.status_code == 200
    titles = {i["title"] for i in checklist.json()}
    assert titles == {"Check main gate lock", "Log visitor book", "Inspect CCTV feed"}
    assert "Totally different item" not in titles


def test_assign_duty_with_unknown_template_404s(client, db, rig):
    import uuid
    r = client.post("/api/v1/staff/duties",
                    json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                          "duty_name": "Gate Round", "duty_date": str(date.today()),
                          "checklist_template_id": str(uuid.uuid4())},
                    headers=rig["admin"]["headers"])
    assert r.status_code == 404


# ── Checklist item completion ────────────────────────────────────────────────

def test_complete_checklist_item(client, db, rig):
    template = client.post("/api/v1/staff/checklist-templates",
                           json=_template_payload(rig["society"].id),
                           headers=rig["admin"]["headers"]).json()
    duty = client.post("/api/v1/staff/duties",
                       json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                             "duty_name": "Gate Round", "duty_date": str(date.today()),
                             "checklist_template_id": template["id"]},
                       headers=rig["admin"]["headers"]).json()
    item_id = duty["checklist_items"][0]["id"]

    r = client.post(f"/api/v1/staff/duties/{duty['id']}/checklist/{item_id}/complete",
                    json={"notes": "Done, all clear"},
                    headers=rig["admin"]["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_completed"] is True
    assert data["completed_at"] is not None
    assert data["notes"] == "Done, all clear"


def test_complete_duty_blocked_until_required_items_done(client, db, rig):
    template = client.post("/api/v1/staff/checklist-templates",
                           json=_template_payload(rig["society"].id),
                           headers=rig["admin"]["headers"]).json()
    duty = client.post("/api/v1/staff/duties",
                       json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                             "duty_name": "Gate Round", "duty_date": str(date.today()),
                             "checklist_template_id": template["id"]},
                       headers=rig["admin"]["headers"]).json()

    guard_user = make_user(db, "chk-guarduser@stf.com", role="Security Staff")
    blocked = client.post(f"/api/v1/staff/duties/{duty['id']}/complete",
                          headers=guard_user["headers"])
    assert blocked.status_code == 409
    assert "checklist" in blocked.json()["detail"].lower()

    required_items = [i for i in duty["checklist_items"] if i["is_required"]]
    for item in required_items:
        r = client.post(f"/api/v1/staff/duties/{duty['id']}/checklist/{item['id']}/complete",
                        json={}, headers=rig["admin"]["headers"])
        assert r.status_code == 200

    completed = client.post(f"/api/v1/staff/duties/{duty['id']}/complete",
                            headers=guard_user["headers"])
    assert completed.status_code == 200, completed.text
    assert completed.json()["is_completed"] is True


def test_optional_item_does_not_block_duty_completion(client, db, rig):
    template_payload = _template_payload(rig["society"].id)
    template_payload["items"] = [{"title": "Optional only", "sequence": 0, "is_required": False}]
    template = client.post("/api/v1/staff/checklist-templates",
                           json=template_payload,
                           headers=rig["admin"]["headers"]).json()
    duty = client.post("/api/v1/staff/duties",
                       json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                             "duty_name": "Light Round", "duty_date": str(date.today()),
                             "checklist_template_id": template["id"]},
                       headers=rig["admin"]["headers"]).json()

    guard_user = make_user(db, "chk-guarduser2@stf.com", role="Security Staff")
    r = client.post(f"/api/v1/staff/duties/{duty['id']}/complete", headers=guard_user["headers"])
    assert r.status_code == 200, r.text


def test_duty_without_template_completes_as_before(client, db, rig):
    """No checklist attached -> unaffected by the new gating."""
    duty = client.post("/api/v1/staff/duties",
                       json={"society_id": str(rig["society"].id), "staff_id": rig["guard"]["id"],
                             "duty_name": "Free-text duty", "duty_date": str(date.today())},
                       headers=rig["admin"]["headers"]).json()
    guard_user = make_user(db, "chk-guarduser3@stf.com", role="Security Staff")
    r = client.post(f"/api/v1/staff/duties/{duty['id']}/complete", headers=guard_user["headers"])
    assert r.status_code == 200
