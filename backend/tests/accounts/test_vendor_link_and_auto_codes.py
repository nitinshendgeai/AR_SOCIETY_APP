"""Expenses name their vendor from the Vendor Master, and the app fills in the references nobody should have to
invent: the next voucher number, a ledger's code, a wing's code, a parking zone's code."""
from datetime import date

from app.utils.auto_code import next_number_code, short_code
from tests.billing.test_budget_suggestions import _rig
from tests.conftest import make_society, make_user
from tests.accounts.test_recurring_expenses import _ledgers, _make, _month, _record

A = "/api/v1/accounts"
V = "/api/v1/vendors"
TODAY = date.today()


def _vendor(client, h, sid, name="Shield Security Services"):
    r = client.post(f"{V}/", headers=h, json={"society_id": str(sid), "company_name": name,
                                             "mobile": "9876543210", "category": "security"})
    assert r.status_code == 201, r.text
    return r.json()


def _payment(client, h, sid, L, **over):
    body = {"society_id": str(sid), "voucher_type": "payment", "voucher_date": str(TODAY), "narration": "Guards",
            "entries": [{"account_id": L["security_charges"]["id"], "debit": "1000"},
                        {"account_id": L["cash"]["id"], "credit": "1000"}], **over}
    return client.post(f"{A}/vouchers", headers=h, json=body)


# ── Vendor Master ↔ expenses ─────────────────────────────────────────────────

def test_an_expense_can_name_a_vendor_from_the_master_and_shows_in_the_vendors_payments(client, db):
    society, admin, _, _ = _rig(db, "vl1")
    L = _ledgers(client, admin, society.id)
    vendor = _vendor(client, admin, society.id)

    r = _payment(client, admin, society.id, L, vendor_id=vendor["id"], reference="BILL-77")
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["vendor_id"] == vendor["id"] and v["vendor_name"] == "Shield Security Services"
    assert v["reference"] == "BILL-77"                                   # the supplier's own number stays typed

    _payment(client, admin, society.id, L)                                # an expense with no vendor
    mine = client.get(f"{A}/vouchers/society/{society.id}", headers=admin, params={"vendor_id": vendor["id"]}).json()
    assert [x["voucher_number"] for x in mine] == [v["voucher_number"]]
    assert len(client.get(f"{A}/vouchers/society/{society.id}", headers=admin).json()) == 2


def test_only_a_vendor_of_this_society_can_be_named_and_only_on_a_payment(client, db):
    society, admin, _, _ = _rig(db, "vl2")
    other = make_society(db, "Other Society vl2")
    other_admin = make_user(db, "other@vl2.com", role="Society Admin")
    other_admin["user"].society_id = other.id
    db.commit()
    foreign = _vendor(client, other_admin["headers"], other.id, "Foreign Vendor")
    L = _ledgers(client, admin, society.id)

    assert _payment(client, admin, society.id, L, vendor_id=foreign["id"]).status_code == 422
    receipt = client.post(f"{A}/vouchers", headers=admin, json={
        "society_id": str(society.id), "voucher_type": "receipt", "voucher_date": str(TODAY),
        "vendor_id": _vendor(client, admin, society.id)["id"],
        "entries": [{"account_id": L["cash"]["id"], "debit": "500"},
                    {"account_id": L["security_charges"]["id"], "credit": "500"}]})
    assert receipt.status_code == 422


def test_editing_a_payment_can_change_its_vendor_and_the_history_keeps_the_old_one(client, db):
    society, admin, _, _ = _rig(db, "vl3")
    L = _ledgers(client, admin, society.id)
    first, second = _vendor(client, admin, society.id, "First Co"), _vendor(client, admin, society.id, "Second Co")
    v = _payment(client, admin, society.id, L, vendor_id=first["id"]).json()
    r = client.put(f"{A}/vouchers/{v['id']}", headers=admin, json={
        "voucher_date": str(TODAY), "narration": "Guards", "vendor_id": second["id"], "reason": "wrong vendor",
        "entries": [{"account_id": L["security_charges"]["id"], "debit": "1000"},
                    {"account_id": L["cash"]["id"], "credit": "1000"}]})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_name"] == "Second Co"
    assert r.json()["revisions"][0]["before"]["vendor_name"] == "First Co"


def test_a_monthly_expense_follows_its_vendor_into_the_voucher_it_records(client, db):
    society, admin, _, _ = _rig(db, "vl4")
    L = _ledgers(client, admin, society.id)
    vendor = _vendor(client, admin, society.id)
    r = _make(client, admin, society.id, L, vendor_id=vendor["id"], payee=None)
    assert r["vendor_id"] == vendor["id"] and r["payee"] == "Shield Security Services"
    v = _record(client, admin, r["id"], _month(0))
    assert v.status_code == 201, v.text
    assert v.json()["vendor_id"] == vendor["id"]

    # unlinking, or typing a payee instead, drops the link
    c = client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"vendor_id": None}).json()
    assert c["vendor_id"] is None and c["payee"] is None
    c = client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"vendor_id": vendor["id"]}).json()
    assert c["vendor_id"] == vendor["id"]
    c = client.patch(f"{A}/recurring-expenses/{r['id']}", headers=admin, json={"payee": "Someone else"}).json()
    assert c["vendor_id"] is None and c["payee"] == "Someone else"


# ── Auto references ──────────────────────────────────────────────────────────

def test_the_next_voucher_number_is_shown_before_saving_and_is_the_one_used(client, db):
    society, admin, _, _ = _rig(db, "ar1")
    L = _ledgers(client, admin, society.id)
    preview = client.get(f"{A}/vouchers/next-number/{society.id}", headers=admin, params={"voucher_type": "payment"})
    assert preview.status_code == 200, preview.text
    saved = _payment(client, admin, society.id, L).json()
    assert saved["voucher_number"] == preview.json()["voucher_number"]
    assert client.get(f"{A}/vouchers/next-number/{society.id}", headers=admin,
                      params={"voucher_type": "payment"}).json()["voucher_number"] != saved["voucher_number"]
    assert client.get(f"{A}/vouchers/next-number/{society.id}", headers=admin,
                      params={"voucher_type": "nonsense"}).status_code == 422


def test_next_voucher_number_is_only_for_your_own_society(client, db):
    society, admin, _, _ = _rig(db, "ar2")
    other = make_society(db, "Other Society ar2")
    theirs = make_user(db, "sb@ar2.test", role="Society Admin")
    theirs["user"].society_id = other.id
    db.commit()
    r = client.get(f"{A}/vouchers/next-number/{society.id}", headers=theirs["headers"],
                   params={"voucher_type": "payment"})
    assert r.status_code == 403


def test_a_new_ledger_without_a_code_gets_the_next_number_in_its_group(client, db):
    society, admin, _, _ = _rig(db, "ar3")
    chart = client.get(f"{A}/chart/{society.id}", headers=admin).json()
    group = next(g for g in chart if g["name"] == "Direct Expenses" or any(a["code"] for a in g["accounts"])
                 and g["nature"] == "expense")
    top = max(int(a["code"]) for a in group["accounts"] if a["code"] and a["code"].isdigit())
    made = client.post(f"{A}/ledgers", headers=admin,
                       json={"society_id": str(society.id), "group_id": group["id"], "name": "Zebra crossing paint"})
    assert made.status_code == 201, made.text
    assert made.json()["code"] == str(top + 1)
    typed = client.post(f"{A}/ledgers", headers=admin, json={"society_id": str(society.id), "group_id": group["id"],
                                                             "name": "Garden waste", "code": "X-1"})
    assert typed.json()["code"] == "X-1"                                  # a code someone chose is kept


def test_a_wing_and_a_parking_zone_without_a_code_get_one_from_their_name(client, db):
    admin = make_user(db, "adm@ar4.com", role="Society Admin")
    society = make_society(db, "Code Society")
    admin["user"].society_id = society.id
    db.commit()
    h = admin["headers"]
    a = client.post("/api/v1/wings/", headers=h, json={"name": "A Wing", "society_id": str(society.id)}).json()
    b = client.post("/api/v1/wings/", headers=h, json={"name": "A Block", "society_id": str(society.id)}).json()
    c = client.post("/api/v1/wings/", headers=h, json={"name": "C Wing", "code": "Z9", "society_id": str(society.id)}).json()
    assert (a["code"], b["code"], c["code"]) == ("A", "A2", "Z9")

    z1 = client.post("/api/v1/parking/zones", headers=h, json={"society_id": str(society.id), "name": "Basement"}).json()
    z2 = client.post("/api/v1/parking/zones", headers=h, json={"society_id": str(society.id), "name": "Open Air"}).json()
    assert (z1["code"], z2["code"]) == ("BAS", "OA")


def test_short_code_and_next_number_helpers():
    assert short_code("A Wing") == "A" and short_code("North Block") == "NORTH"
    assert short_code("Basement") == "BAS" and short_code("Open Air Parking") == "OA"
    assert short_code("A Wing", ["a"]) == "A2" and short_code("A Wing", ["A", "A2"]) == "A3"
    assert short_code("") == "X"
    assert next_number_code(["1001", "1106", None, "X-1"]) == "1107" and next_number_code([None, "AB"]) is None
