"""The stores: items and their stock, stock in, issuing to people (returnable or used up), returns, and the numbers
the Stores screen shows."""
from datetime import date, timedelta
from uuid import UUID

import pytest

from tests.conftest import make_society, make_user

API = "/api/v1/inventory"


def _member(db, email, role, society, name=None):
    who = make_user(db, email, role=role, full_name=name or email.split("@")[0])
    who["user"].society_id = society.id
    db.commit()
    return who


def _staff(db, society, code, name):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    s = Staff(society_id=society.id, employee_code=code, full_name=name, mobile=f"90{abs(hash(code)) % 99999999:08d}",
              department=StaffDepartment.HOUSEKEEPING, status=StaffStatus.ACTIVE)
    db.add(s); db.commit(); db.refresh(s)
    return s


@pytest.fixture
def st(db):
    society = make_society(db, "Stores Society")
    other = make_society(db, "Other Stores Society")
    r = {
        "society": society,
        "admin": _member(db, "admin@stores.test", "Society Admin", society, "Asha Admin"),
        "mgr": _member(db, "mgr@stores.test", "Manager", society, "Manoj Manager"),
        "guard": _member(db, "guard@stores.test", "Security Staff", society, "Gopal Guard"),
        "res": _member(db, "res@stores.test", "Resident", society),
        "other_admin": _member(db, "admin@other-stores.test", "Society Admin", other),
        "staff": _staff(db, society, "HK-1", "Hema Housekeeper"),
    }
    return r


def _item(client, who, name="Floor cleaner", minimum=5, **over):
    r = client.post(f"{API}/items", headers=who["headers"], json={
        "name": name, "category": "cleaning", "unit_type": "litre", "minimum_stock": minimum, **over})
    assert r.status_code == 201, r.text
    return r.json()


def _in(client, who, item, qty, **over):
    r = client.post(f"{API}/stock/in", headers=who["headers"], json={"item_id": item["id"], "quantity": qty, **over})
    assert r.status_code == 200, r.text
    return r.json()


def _issue(client, who, item, qty, **over):
    return client.post(f"{API}/issues", headers=who["headers"], json={"item_id": item["id"], "quantity_issued": qty, **over})


# ── Items ─────────────────────────────────────────────────────────────────────

def test_an_item_needs_a_name_and_sane_numbers(client, st):
    h = st["admin"]["headers"]
    base = {"category": "cleaning", "unit_type": "litre"}
    assert client.post(f"{API}/items", headers=h, json={**base, "name": "  "}).status_code == 422
    assert client.post(f"{API}/items", headers=h, json={**base, "name": "A", "minimum_stock": -1}).status_code == 422
    assert client.post(f"{API}/items", headers=h, json={**base, "name": "A", "unit_cost": -5}).status_code == 422


def test_an_item_name_is_not_repeated(client, st):
    _item(client, st["admin"], "Mop")
    r = client.post(f"{API}/items", headers=st["admin"]["headers"], json={"name": "mop", "category": "cleaning"})
    assert r.status_code == 409


def test_the_item_says_whether_it_is_low(client, st):
    item = _item(client, st["admin"], minimum=5)
    assert item["is_low_stock"] is True and item["current_stock"] == 0
    _in(client, st["admin"], item, 20)
    got = client.get(f"{API}/items/{item['id']}", headers=st["admin"]["headers"]).json()
    assert got["current_stock"] == 20 and got["is_low_stock"] is False


def test_who_may_keep_the_stores(client, st):
    assert client.post(f"{API}/items", headers=st["res"]["headers"], json={"name": "X", "category": "other"}).status_code == 403
    item = _item(client, st["mgr"])
    assert client.post(f"{API}/stock/in", headers=st["guard"]["headers"], json={"item_id": item["id"], "quantity": 1}).status_code == 403
    assert client.patch(f"{API}/items/{item['id']}", headers=st["guard"]["headers"], json={"name": "Y"}).status_code == 403


def test_stock_in_cost_cannot_be_negative_and_the_count_needs_a_reason(client, st):
    item = _item(client, st["admin"])
    h = st["admin"]["headers"]
    assert client.post(f"{API}/stock/in", headers=h, json={"item_id": item["id"], "quantity": 2, "unit_cost": -1}).status_code == 422
    assert client.post(f"{API}/stock/adjust", headers=h, json={"item_id": item["id"], "new_quantity": 3, "notes": "  "}).status_code == 422
    assert client.post(f"{API}/stock/adjust", headers=h, json={"item_id": item["id"], "new_quantity": -1, "notes": "x"}).status_code == 422
    r = client.post(f"{API}/stock/adjust", headers=h, json={"item_id": item["id"], "new_quantity": 3, "notes": "Stock count"})
    assert r.status_code == 200 and r.json()["current_quantity"] == 3


def test_an_item_can_be_renamed_and_recategorised_but_not_retired_while_stocked_or_out(client, st):
    h = st["admin"]["headers"]
    item = _item(client, st["admin"], "Mop")
    other = _item(client, st["admin"], "Bucket")
    assert client.patch(f"{API}/items/{item['id']}", headers=h, json={"name": "bucket"}).status_code == 409
    r = client.patch(f"{API}/items/{item['id']}", headers=h, json={"name": "Wet mop", "category": "housekeeping"})
    assert r.status_code == 200 and r.json()["name"] == "Wet mop" and r.json()["category"] == "housekeeping"
    _in(client, st["admin"], other, 4)
    assert client.patch(f"{API}/items/{other['id']}", headers=h, json={"is_active": False}).status_code == 409
    client.post(f"{API}/stock/adjust", headers=h, json={"item_id": other["id"], "new_quantity": 0, "notes": "all gone"})
    assert client.patch(f"{API}/items/{other['id']}", headers=h, json={"is_active": False}).status_code == 200
    listed = client.get(f"{API}/items/society/{st['society'].id}", headers=h).json()
    assert other["id"] not in [i["id"] for i in listed]
    assert _issue(client, st["admin"], other, 1, issued_to_staff=str(st["staff"].id)).status_code in (404, 409)


# ── Issuing ───────────────────────────────────────────────────────────────────

def test_an_issue_needs_someone_to_give_it_to_and_enough_stock(client, st):
    item = _item(client, st["admin"])
    _in(client, st["admin"], item, 5)
    assert _issue(client, st["admin"], item, 1).status_code == 422
    r = _issue(client, st["admin"], item, 9, issued_to_staff=str(st["staff"].id))
    assert r.status_code == 409 and "Insufficient" in r.json()["detail"]


def test_issue_to_a_staff_member_shows_names_and_what_is_outstanding(client, st):
    item = _item(client, st["admin"], "Torch")
    _in(client, st["admin"], item, 10)
    r = _issue(client, st["mgr"], item, 4, issued_to_staff=str(st["staff"].id), purpose="Night rounds",
               expected_return_date=str(date.today() + timedelta(days=3)))
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["item_name"] == "Torch" and row["issued_to_name"] == "Hema Housekeeper"
    assert row["issued_by_name"] == "Manoj Manager"
    assert row["outstanding"] == 4 and row["overdue"] is False and row["status"] == "issued"


def test_the_issue_must_stay_inside_the_society(client, st, db):
    item = _item(client, st["admin"])
    _in(client, st["admin"], item, 5)
    foreign = _staff(db, make_society(db, "Third Society"), "HK-9", "Far Away")
    assert _issue(client, st["admin"], item, 1, issued_to_staff=str(foreign.id)).status_code == 422
    import uuid
    assert _issue(client, st["admin"], item, 1, issued_to_staff=str(st["staff"].id),
                  complaint_id=str(uuid.uuid4())).status_code == 422


def test_the_return_date_cannot_be_in_the_past(client, st):
    item = _item(client, st["admin"])
    _in(client, st["admin"], item, 5)
    r = _issue(client, st["admin"], item, 1, issued_to_staff=str(st["staff"].id),
               expected_return_date=str(date.today() - timedelta(days=2)))
    assert r.status_code == 422


def test_used_up_items_are_consumed_not_returnable(client, st):
    h = st["admin"]["headers"]
    item = _item(client, st["admin"])
    _in(client, st["admin"], item, 10)
    r = _issue(client, st["admin"], item, 3, issued_to_staff=str(st["staff"].id), consumed=True,
               expected_return_date=str(date.today() + timedelta(days=2)))
    assert r.status_code == 201
    row = r.json()
    assert row["status"] == "consumed" and row["outstanding"] == 0 and row["expected_return_date"] is None
    assert client.post(f"{API}/returns", headers=h, json={"issue_id": row["id"], "quantity": 1}).status_code == 409
    assert client.get(f"{API}/stock/{item['id']}", headers=h).json()["current_quantity"] == 7
    kinds = [t["transaction_type"] for t in client.get(f"{API}/transactions/{item['id']}", headers=h).json()]
    assert "consumption" in kinds


def test_returns_are_checked_and_move_the_status_on(client, st):
    h = st["admin"]["headers"]
    item = _item(client, st["admin"])
    _in(client, st["admin"], item, 10)
    row = _issue(client, st["admin"], item, 4, issued_to_staff=str(st["staff"].id)).json()
    ret = lambda q, **o: client.post(f"{API}/returns", headers=h, json={"issue_id": row["id"], "quantity": q, **o})
    assert ret(0).status_code == 422 and ret(-1).status_code == 422
    assert ret(5).status_code == 409
    part = ret(1).json()
    assert part["status"] == "partially_returned" and part["outstanding"] == 3
    assert ret(3, condition="damaged").json()["status"] == "returned"
    assert ret(1).status_code == 409
    # the damaged three did not go back on the shelf: 10 - 4 + 1
    assert client.get(f"{API}/stock/{item['id']}", headers=h).json()["current_quantity"] == 7


def test_issue_list_filters_open_overdue_and_item(client, st, db):
    from app.modules.inventory.models.inventory import InventoryIssue
    h = st["admin"]["headers"]
    a, b = _item(client, st["admin"], "Ladder"), _item(client, st["admin"], "Gloves")
    _in(client, st["admin"], a, 5); _in(client, st["admin"], b, 5)
    late = _issue(client, st["admin"], a, 1, issued_to_staff=str(st["staff"].id),
                  expected_return_date=str(date.today() + timedelta(days=1))).json()
    # make it overdue by moving its date back
    row = db.query(InventoryIssue).filter(InventoryIssue.id == UUID(late["id"])).one()
    row.expected_return_date = date.today() - timedelta(days=3); db.commit()
    done = _issue(client, st["admin"], b, 1, issued_to_staff=str(st["staff"].id)).json()
    client.post(f"{API}/returns", headers=h, json={"issue_id": done["id"], "quantity": 1})
    q = lambda **p: client.get(f"{API}/issues/society/{st['society'].id}", headers=h, params=p).json()
    assert len(q()) == 2
    assert [i["id"] for i in q(status="open")] == [late["id"]]
    over = q(status="overdue")
    assert [i["id"] for i in over] == [late["id"]] and over[0]["overdue"] is True
    assert [i["id"] for i in q(item_id=b["id"])] == [done["id"]]
    assert [i["id"] for i in q(status="returned")] == [done["id"]]


# ── History, summary, society ─────────────────────────────────────────────────

def test_history_names_who_did_it(client, st):
    h = st["admin"]["headers"]
    item = _item(client, st["admin"])
    _in(client, st["mgr"], item, 8, notes="Bill 114")
    rows = client.get(f"{API}/transactions/{item['id']}", headers=h).json()
    assert rows[0]["transaction_type"] == "stock_in" and rows[0]["performed_by_name"] == "Manoj Manager"
    assert rows[0]["quantity_before"] == 0 and rows[0]["quantity_after"] == 8


def test_the_summary_counts_what_matters(client, st, db):
    from app.modules.inventory.models.inventory import InventoryIssue
    h = st["admin"]["headers"]
    full = _item(client, st["admin"], "Brooms", minimum=2, unit_cost=100)
    low = _item(client, st["admin"], "Soap", minimum=10, unit_cost=50)
    _item(client, st["admin"], "Empty one", minimum=0)
    _in(client, st["admin"], full, 10); _in(client, st["admin"], low, 4)
    row = _issue(client, st["admin"], full, 2, issued_to_staff=str(st["staff"].id),
                 expected_return_date=str(date.today() + timedelta(days=1))).json()
    db.query(InventoryIssue).filter(InventoryIssue.id == UUID(row["id"])).one().expected_return_date = date.today() - timedelta(days=1)
    db.commit()
    s = client.get(f"{API}/summary/{st['society'].id}", headers=h).json()
    assert s["items"] == 3 and s["low_stock"] == 2 and s["out_of_stock"] == 1
    assert s["stock_value"] == 8 * 100 + 4 * 50
    assert s["out_with_people"] == 1 and s["overdue_returns"] == 1
    assert client.get(f"{API}/summary/{st['society'].id}", headers=st["guard"]["headers"]).status_code == 403


def test_another_society_sees_none_of_it(client, st):
    item = _item(client, st["admin"])
    _in(client, st["admin"], item, 5)
    row = _issue(client, st["admin"], item, 1, issued_to_staff=str(st["staff"].id)).json()
    o = st["other_admin"]["headers"]
    assert client.get(f"{API}/summary/{st['society'].id}", headers=o).status_code == 403
    assert client.get(f"{API}/issues/society/{st['society'].id}", headers=o).status_code == 403
    assert client.get(f"{API}/transactions/{item['id']}", headers=o).status_code == 404
    assert client.post(f"{API}/returns", headers=o, json={"issue_id": row["id"], "quantity": 1}).status_code == 404
