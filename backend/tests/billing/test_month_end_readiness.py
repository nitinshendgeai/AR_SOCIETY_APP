"""Making the actual-expense billing as easy as the books: a society can let its admin's payments post without a second
approver; waiting payments are approved in one go; the cycle preview carries a month-end checklist (what is waiting,
what no element covers, which heads found no spend); and the heads are switched to actual expenses together."""
from datetime import date, timedelta
from decimal import Decimal

from app.modules.accounts.models.accounts import Voucher
from tests.accounts.test_accounts import _ledgers
from tests.billing.test_budget_suggestions import _bill, _charge_from_element, _rig
from tests.billing.test_period_expense_billing import _cycle_dates, _period_head, _preview
from tests.conftest import make_user

A = "/api/v1/accounts"
B = "/api/v1/billing"


def _join(db, member, society):
    member["user"].society_id = society.id
    db.commit()
    return member


def _payment(client, h, sid, L, amount="450", key="security_charges"):
    return client.post(f"{A}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": str(date.today()), "narration": "Guard",
        "entries": [{"account_id": L[key]["id"], "debit": amount}, {"account_id": L["cash"]["id"], "credit": amount}]})


def _admin_rig(client, db, tag):
    society, _admin, manager, _res = _rig(db, tag)
    admin = _join(db, make_user(db, f"adm2@{tag}.com", role="Society Admin", full_name="Asha Admin"), society)
    return society, admin["headers"], manager, str(society.id)


# ── Who approves a payment ────────────────────────────────────────────────────

def test_a_payment_still_waits_for_a_second_approver_unless_the_society_chooses_otherwise(client, db):
    society, admin, manager, sid = _admin_rig(client, db, "m1")
    L = _ledgers(client, admin, sid)
    assert _payment(client, admin, sid, L).json()["approval_status"] == "pending"          # the default is unchanged
    assert client.get(f"{B}/maintenance-settings/{sid}", headers=admin).json()["auto_approve_admin_expenses"] is False

    r = client.put(f"{B}/maintenance-settings/{sid}", json={"auto_approve_admin_expenses": True}, headers=admin)
    assert r.status_code == 200 and r.json()["auto_approve_admin_expenses"] is True
    v = _payment(client, admin, sid, L, "700").json()
    assert v["approval_status"] == "approved" and v["approved_by_name"] == "Asha Admin"
    assert "skip the second approval" in v["approval_note"]


def test_only_a_payment_by_someone_who_could_approve_it_posts_directly(client, db):
    society, admin, manager, sid = _admin_rig(client, db, "m2")
    client.put(f"{B}/maintenance-settings/{sid}", json={"auto_approve_admin_expenses": True}, headers=admin)
    L = _ledgers(client, admin, sid)
    assert _payment(client, manager, sid, L).json()["approval_status"] == "pending"     # a manager's still waits
    journal = client.post(f"{A}/vouchers", headers=admin, json={
        "society_id": sid, "voucher_type": "journal", "voucher_date": str(date.today()),
        "entries": [{"account_id": L["security_charges"]["id"], "debit": "10"},
                    {"account_id": L["repairs_plumbing"]["id"], "credit": "10"}]})
    assert journal.status_code == 201, journal.text
    assert journal.json()["approval_status"] == "pending"                                          # nor does a journal


def test_a_manager_cannot_turn_off_the_second_approver(client, db):
    society, admin, manager, sid = _admin_rig(client, db, "m3")
    r = client.put(f"{B}/maintenance-settings/{sid}", json={"auto_approve_admin_expenses": True},
                   headers=manager)
    assert r.status_code == 403
    assert client.get(f"{B}/maintenance-settings/{sid}", headers=admin).json()["auto_approve_admin_expenses"] is False
    # a manager can still change the other rules
    assert client.put(f"{B}/maintenance-settings/{sid}", json={"interest_grace_days": 3},
                      headers=manager).status_code == 200


# ── Approving what is waiting, in one go ──────────────────────────────────────

def test_waiting_payments_are_approved_together_and_one_s_own_entries_wait_for_someone_else(client, db):
    society, *_ = _rig(db, "m4")
    admin = _join(db, make_user(db, "adm@m4.com", role="Society Admin", full_name="Asha Admin"), society)
    chair = _join(db, make_user(db, "chair@m4.com", role="Committee Chairman", full_name="Raj Chair"), society)
    sid = str(society.id)
    L = _ledgers(client, admin["headers"], sid)
    mine = [_payment(client, admin["headers"], sid, L, a).json() for a in ("100", "200")]
    theirs = _payment(client, chair["headers"], sid, L, "400").json()

    r = client.post(f"{A}/vouchers/{sid}/approve-pending", json={}, headers=admin["headers"])
    assert r.status_code == 200 and r.json() == {"approved": 1, "left_for_another_approver": 2, "amount": "400.00"}
    db.expire_all()
    status = {v.amount: v.approval_status for v in db.query(Voucher).filter_by(society_id=society.id)}
    assert status[Decimal("400.00")] == "approved" and status[Decimal("100.00")] == "pending"

    r = client.post(f"{A}/vouchers/{sid}/approve-pending", json={}, headers=chair["headers"])
    assert r.json()["approved"] == 2 and r.json()["left_for_another_approver"] == 0
    assert theirs["id"] and all(m["id"] for m in mine)


def test_bulk_approval_can_be_limited_to_a_date_range_and_needs_an_approver(client, db):
    society, admin, manager, sid = _admin_rig(client, db, "m5")
    L = _ledgers(client, admin, sid)
    _payment(client, manager, sid, L)
    r = client.post(f"{A}/vouchers/{sid}/approve-pending", json={"date_to": str(date.today() - timedelta(days=1))},
                    headers=admin)
    assert r.json()["approved"] == 0                                                    # dated today: outside the range
    assert client.post(f"{A}/vouchers/{sid}/approve-pending", json={}, headers=manager).status_code == 403
    assert client.post(f"{A}/vouchers/{sid}/approve-pending", json={}, headers=admin).json()["approved"] == 1


# ── The month-end checklist ───────────────────────────────────────────────────

def _cycle_setup(client, db, tag):
    society, admin, manager, _ = _rig(db, tag)
    head = _period_head(client, manager, society.id)
    today = date.today()
    cid = _cycle_dates(client, manager, society.id, today - timedelta(days=10), today + timedelta(days=20), f"C {tag}")
    return society, admin, manager, head, cid


def test_the_checklist_is_empty_when_no_head_bills_actual_expenses(client, db):
    society, admin, manager, _ = _rig(db, "r0")
    _charge_from_element(client, manager, society.id, "housekeeping", basis="fixed", default_amount="450")
    cid = _cycle_dates(client, manager, society.id, date.today(), date.today() + timedelta(days=30), "Plain")
    ready = _preview(client, manager, cid)["readiness"]
    assert ready["applies"] is False and ready["ready"] is True


def test_the_checklist_reports_what_is_waiting_unlinked_uncovered_and_without_spend(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r1")
    _charge_from_element(client, manager, society.id, "security", basis="budget_equal", default_amount="1")
    _bill(client, admin, society.id, "housekeeping", "3000.00", date.today())      # counted
    _bill(client, admin, society.id, "plumbing", "800.00", date.today())           # a ledger no element covers
    _bill(client, admin, society.id, "security", "500.00", date.today())           # an element whose head is not on actual expenses
    _bill(client, admin, society.id, "housekeeping", "250.00", date.today())       # will be left waiting
    waiting = [v for v in db.query(Voucher).filter_by(society_id=society.id) if round(v.amount) == 250][0]
    waiting.approval_status = "pending"
    db.commit()

    ready = _preview(client, manager, cid)["readiness"]
    assert ready["applies"] is True and ready["ready"] is False
    assert ready["pending_count"] == 1 and ready["pending_amount"] == "250.00"
    assert [u["amount"] for u in ready["unlinked_ledgers"]] == ["800.00"]
    assert ready["unlinked_ledgers"][0]["account_id"]
    assert [(e["element_name"], e["amount"]) for e in ready["uncovered_elements"]] == [("Security Services", "500.00")]
    assert ready["heads_without_spend"] == []


def test_the_checklist_is_clear_when_everything_is_in_order(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r2")
    _bill(client, admin, society.id, "housekeeping", "3000.00", date.today())
    ready = _preview(client, manager, cid)["readiness"]
    assert ready["ready"] is True and ready["pending_count"] == 0 and ready["unlinked_ledgers"] == []


def test_a_head_that_found_no_spend_is_named(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r3")
    ready = _preview(client, manager, cid)["readiness"]
    assert ready["heads_without_spend"] == [head["name"]] and ready["ready"] is False


def test_a_ledger_can_be_linked_from_the_checklist(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r4")
    _bill(client, admin, society.id, "housekeeping", "3000.00", date.today())
    _bill(client, admin, society.id, "plumbing", "800.00", date.today())
    ready = _preview(client, manager, cid)["readiness"]
    acc = ready["unlinked_ledgers"][0]["account_id"]
    housekeeping = next(e for e in client.get(f"{B}/elements/{society.id}", headers=manager).json()
                        if e["code"] == "housekeeping")
    assert client.patch(f"/api/v1/accounts/ledgers/{acc}", json={"maintenance_element_id": housekeeping["id"]},
                        headers=admin).status_code == 200
    pv = _preview(client, manager, cid)
    assert pv["readiness"]["unlinked_ledgers"] == [] and pv["expense_allocations"][0]["pool_amount"] == "3800.00"


# ── Switching the heads together ──────────────────────────────────────────────

def test_heads_are_switched_to_actual_expenses_together_and_the_unfit_ones_say_why(client, db):
    society, admin, manager, _ = _rig(db, "b1")
    hk = _charge_from_element(client, manager, society.id, "housekeeping", basis="fixed", default_amount="450")
    sec = _charge_from_element(client, manager, society.id, "security", default_amount="1")          # annual budget
    sink = _charge_from_element(client, manager, society.id, "sinking_fund")                         # % of construction cost
    plain = client.post(f"{B}/charges", headers=manager, json={
        "society_id": str(society.id), "charge_type": "maintenance", "name": "Misc", "default_amount": "10"}).json()
    r = client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager,
                    json={"charge_ids": [hk["id"], sec["id"], sink["id"], plain["id"]]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert sorted(c["name"] for c in out["changed"]) == sorted([hk["name"], sec["name"]])
    assert all(c["auto_from_expenses"] and c["expense_mode"] == "period" for c in out["changed"])
    reasons = {s["name"]: s["reason"] for s in out["skipped"]}
    assert "spend-based" in reasons[sink["name"]] and "element" in reasons["Misc"]
    heads = {c["name"]: c for c in client.get(f"{B}/charges/{society.id}", headers=manager).json()}
    assert heads[hk["name"]]["expense_mode"] == "period" and heads[sink["name"]]["auto_from_expenses"] is False


def test_only_one_head_per_element_is_switched_and_another_society_is_refused(client, db):
    society, admin, manager, _ = _rig(db, "b2")
    first = _charge_from_element(client, manager, society.id, "housekeeping", basis="fixed", default_amount="1")
    elements = {e["code"]: e["id"] for e in client.get(f"{B}/elements/{society.id}", headers=manager).json()}
    second = client.post(f"{B}/charges", headers=manager, json={
        "society_id": str(society.id), "element_id": elements["housekeeping"], "name": "Housekeeping extra",
        "basis": "per_sqft", "default_amount": "1"}).json()
    out = client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager,
                      json={"charge_ids": [first["id"], second["id"]]}).json()
    assert [c["id"] for c in out["changed"]] == [first["id"]]
    assert "already bills this element" in out["skipped"][0]["reason"]

    other, oadmin, omanager, _ = _rig(db, "b2b")
    foreign = _charge_from_element(client, omanager, other.id, "housekeeping", basis="fixed", default_amount="1")
    out = client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager,
                      json={"charge_ids": [foreign["id"]]}).json()
    assert out["changed"] == [] and "not a charge head of this society" in out["skipped"][0]["reason"].lower()


def test_what_the_checklist_shows_is_not_repeated_in_the_plain_warnings(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r5")
    _bill(client, admin, society.id, "plumbing", "800.00", date.today())
    _bill(client, admin, society.id, "housekeeping", "250.00", date.today())
    waiting = [v for v in db.query(Voucher).filter_by(society_id=society.id) if round(v.amount) == 250][0]
    waiting.approval_status = "pending"
    db.commit()
    pv = _preview(client, manager, cid)
    assert pv["readiness"]["pending_count"] == 1 and pv["readiness"]["unlinked_ledgers"]
    assert not any("waiting for approval" in w or "no maintenance element covers" in w or "nothing is billed" in w
                   for w in pv["warnings"])


def test_an_element_with_spend_but_no_head_gets_one_that_bills_actual_expenses(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r6")
    _bill(client, admin, society.id, "housekeeping", "3000.00", date.today())
    _bill(client, admin, society.id, "security", "500.00", date.today())
    ready = _preview(client, manager, cid)["readiness"]
    assert [(e["element_name"], e["has_head"]) for e in ready["uncovered_elements"]] == [("Security Services", False)]

    element_id = ready["uncovered_elements"][0]["element_id"]
    r = client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager, json={"element_ids": [element_id]})
    assert r.status_code == 200, r.text
    made = r.json()["changed"]
    assert [(c["name"], c["element_id"], c["expense_mode"], c["auto_from_expenses"]) for c in made] == \
        [("Security Services", element_id, "period", True)]
    pv = _preview(client, manager, cid)
    assert pv["readiness"]["uncovered_elements"] == []
    assert {a["charge_name"]: a["pool_amount"] for a in pv["expense_allocations"]} == {
        head["name"]: "3000.00", "Security Services": "500.00"}
    # asking again changes nothing and makes no second head
    again = client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager,
                        json={"element_ids": [element_id]}).json()
    assert [c["id"] for c in again["changed"]] == [made[0]["id"]]
    assert len([c for c in client.get(f"{B}/charges/{society.id}", headers=manager).json()
                if c["element_id"] == element_id]) == 1


def test_an_element_whose_head_is_a_typed_rate_has_that_head_switched_not_a_second_one_made(client, db):
    society, admin, manager, head, cid = _cycle_setup(client, db, "r7")
    typed = _charge_from_element(client, manager, society.id, "security", basis="fixed", default_amount="450")
    _bill(client, admin, society.id, "security", "500.00", date.today())
    ready = _preview(client, manager, cid)["readiness"]
    assert [(e["element_name"], e["has_head"]) for e in ready["uncovered_elements"]] == [("Security Services", True)]
    out = client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager,
                      json={"element_ids": [ready["uncovered_elements"][0]["element_id"]]}).json()
    assert [c["id"] for c in out["changed"]] == [typed["id"]] and out["changed"][0]["expense_mode"] == "period"


def test_choosing_nothing_is_refused(client, db):
    society, admin, manager, _ = _rig(db, "r8")
    assert client.post(f"{B}/charges/{society.id}/bill-actual-expenses", headers=manager, json={}).status_code == 422
