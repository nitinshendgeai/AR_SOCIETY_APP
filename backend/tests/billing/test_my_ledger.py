"""A resident's own ledger balance: what they owe, any advance paid ahead, and the latest lines (read-only, own flats only)."""
from datetime import date
from decimal import Decimal

from tests.billing.test_advance_import import _post, _row
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig

URL = "/api/v1/billing/bills/me/ledger"


def _issue_bills(client, h, society):
    _charge(client, h, society.id, amount="2500.00")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200


def _one(client, headers, **params):
    r = client.get(URL, params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_flat_with_nothing_posted_yet_shows_a_zero_balance(client, db):
    society, flat1, _f2, _mgr, resident, _other = _rig(db, "led1")
    body = _one(client, resident["headers"])
    assert body["as_of"] == date.today().isoformat()
    [f] = body["flats"]
    assert f["flat_id"] == str(flat1.id) and f["flat_label"] == "Tower A-101"
    assert (f["dues"], f["advance"], f["balance"], f["lines"]) == ("0.00", "0.00", "0.00", [])


def test_the_balance_is_dues_less_advance_with_dr_when_owing_and_cr_when_in_credit(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "led2")
    h = manager["headers"]
    assert _post(client, h, [_row(2, "101", "6000")], society=society).json()[0]["status"] == "recorded"

    [f] = _one(client, resident["headers"])["flats"]                 # paid ahead, nothing billed yet: in credit
    assert (f["advance"], f["balance"], f["balance_dr_cr"]) == ("6000.00", "6000.00", "Cr")

    _issue_bills(client, h, society)                                    # 2,500 billed: flat 101 uses its advance, 102 owes
    [mine] = _one(client, resident["headers"])["flats"]
    assert (mine["advance"], mine["balance"], mine["balance_dr_cr"]) == ("3500.00", "3500.00", "Cr")
    [theirs] = _one(client, other["headers"])["flats"]
    assert theirs["flat_label"] == "Tower A-102"
    assert (theirs["dues"], theirs["advance"], theirs["balance"], theirs["balance_dr_cr"]) == (
        "2500.00", "0.00", "2500.00", "Dr")
    bills = client.get("/api/v1/billing/bills/me", headers=other["headers"]).json()
    assert Decimal(theirs["balance"]) == Decimal(bills["total_outstanding"])      # the same figure My Bills shows as due


def test_the_latest_lines_are_listed_newest_first_without_any_internal_ids(client, db):
    society, flat1, _f2, manager, resident, _other = _rig(db, "led3")
    _issue_bills(client, manager["headers"], society)
    [f] = _one(client, resident["headers"])["flats"]
    assert f["lines"], "the bill appears as a ledger line"
    first = f["lines"][0]
    assert set(first) == {"date", "narration", "debit", "credit", "balance", "balance_dr_cr"}
    assert first["debit"] == "2500.00" and first["balance_dr_cr"] == "Dr"
    text = str(f)
    assert "voucher" not in text.lower() and "reconcil" not in text.lower() and "member_entity" not in text


def test_a_resident_sees_only_their_own_flat_and_cannot_ask_for_another(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "led4")
    mine = _one(client, resident["headers"])
    assert [f["flat_label"] for f in mine["flats"]] == ["Tower A-101"]
    assert client.get(URL, params={"flat_id": str(flat2.id)}, headers=resident["headers"]).status_code == 404
    assert [f["flat_label"] for f in _one(client, resident["headers"], flat_id=str(flat1.id))["flats"]] == ["Tower A-101"]
    assert [f["flat_label"] for f in _one(client, other["headers"])["flats"]] == ["Tower A-102"]


def test_someone_in_another_society_sees_nothing_of_this_one(client, db):
    from app.models.resident import Resident
    from tests.conftest import make_flat, make_society, make_user, make_wing, place_in
    society, flat1, _f2, manager, resident, _other = _rig(db, "led5a")
    _issue_bills(client, manager["headers"], society)
    away = make_society(db, "Away Society")
    away_flat = make_flat(db, make_wing(db, away.id, "W").id, "7")
    outsider = make_user(db, "led5-out@x.test", role="Resident")
    place_in(db, outsider, away)
    db.add(Resident(full_name="Out Sider", flat_id=away_flat.id, user_id=outsider["user"].id, is_primary=True))
    db.commit()
    [f] = _one(client, outsider["headers"])["flats"]
    assert f["flat_label"] == "W-7" and f["balance"] == "0.00" and f["lines"] == []
    assert client.get(URL, params={"flat_id": str(flat1.id)}, headers=outsider["headers"]).status_code == 404


def test_a_login_is_needed(client, db):
    assert client.get(URL).status_code in (401, 403)


def test_a_person_with_no_flat_gets_an_empty_list(client, db):
    from tests.conftest import make_society, make_user, place_in
    society = make_society(db, "No Flat Society")
    nobody = make_user(db, "led7@x.test", role="Resident")
    place_in(db, nobody, society)
    assert _one(client, nobody["headers"])["flats"] == []
