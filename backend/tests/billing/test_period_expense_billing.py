"""A charge head that bills the ACTUAL approved expenses of the cycle's own period, shared out exactly - and the
working kept with the bills. (The trailing "budget from expenses" mode is covered in test_budget_suggestions.py and
test_expense_links_and_flat_charges.py.)"""
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import (
    BillingExpenseAllocation, BillingExpenseSource, BillStatus, InvoiceLineItem, MaintenanceBill,
)
from app.modules.billing.services.period_expenses import allocate_exact
from tests.billing.test_bill_pdf import _bill_pdf
from tests.billing.test_budget_suggestions import _bill, _charge_from_element, _rig

B = "/api/v1/billing"
D = Decimal


def _cycle_dates(client, h, society_id, start, end, name):
    r = client.post(f"{B}/cycles", json={
        "society_id": str(society_id), "name": name, "cycle_start": str(start), "cycle_end": str(end),
        "due_date": str(end + timedelta(days=10))}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _period_head(client, h, society_id, code="housekeeping", basis="per_sqft", **extra):
    return _charge_from_element(client, h, society_id, code, basis=basis, default_amount="1",
                                auto_from_expenses=True, expense_mode="period", **extra)


def _setup(client, db, tag, basis="per_sqft"):
    """Three flats of 1000, 1000 and 2000 sq ft; a housekeeping head billing the period's actual spend."""
    society, admin, manager, _ = _rig(db, tag)
    head = _period_head(client, manager, society.id, basis=basis)
    today = date.today()
    start, end = today - timedelta(days=10), today + timedelta(days=20)
    cycle_id = _cycle_dates(client, manager, society.id, start, end, f"Cycle {tag}")
    return society, admin, manager, head, cycle_id, start, end


def _preview(client, h, cycle_id):
    r = client.get(f"{B}/cycles/{cycle_id}/preview", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _line_for(preview, head_name):
    return {f["flat_label"]: next(l for l in f["lines"] if l["description"] == head_name)
            for f in preview["flats"] if any(l["description"] == head_name for l in f["lines"])}


# ── The exact split ───────────────────────────────────────────────────────────

def test_allocate_exact_always_adds_up_to_the_pool_to_the_paisa():
    rng = random.Random(7)
    for _ in range(300):
        n = rng.randint(1, 40)
        pool = D(rng.randint(1, 5_000_000)) / 100
        weights = {i: D(rng.randint(1, 5000)) / D(rng.choice([1, 3, 7, 12])) for i in range(n)}
        out = allocate_exact(pool, weights)
        assert sum(out.values()) == pool
        assert all(v >= 0 for v in out.values())
        exact = {i: pool * w / sum(weights.values()) for i, w in weights.items()}
        assert all(abs(out[i] - exact[i]) <= D("0.01") for i in weights)      # never more than a paisa off
    assert allocate_exact(D("0"), {1: D(1)}) == {}
    assert allocate_exact(D("100"), {}) == {}
    assert allocate_exact(D("100"), {1: D(0), 2: D(1)}) == {2: D("100.00")}   # a zero weight carries nothing


def test_a_pool_that_does_not_divide_evenly_is_still_billed_to_the_last_paisa(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p1")
    _bill(client, admin, society.id, "housekeeping", "10000.01", date.today())
    pv = _preview(client, manager, cycle_id)
    lines = _line_for(pv, head["name"])
    amounts = sorted(D(l["amount"]) for l in lines.values())
    assert amounts == [D("2500.00"), D("2500.00"), D("5000.01")]        # 1000 : 1000 : 2000 sq ft, penny to the largest fraction
    assert sum(amounts) == D("10000.01")
    alloc = pv["expense_allocations"][0]
    assert alloc["pool_amount"] == "10000.01" and alloc["allocated_amount"] == "10000.01"
    assert alloc["method"] == "area" and alloc["eligible_flats"] == 3
    assert alloc["rate"] == "2.5000"                                     # Rs per sq ft for the full period
    assert [s["amount"] for s in alloc["sources"]] == ["10000.01"]


def test_equal_bases_share_the_pool_equally(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p2", basis="fixed")
    _bill(client, admin, society.id, "housekeeping", "10000.00", date.today())
    pv = _preview(client, manager, cycle_id)
    amounts = sorted(D(l["amount"]) for l in _line_for(pv, head["name"]).values())
    assert amounts == [D("3333.33"), D("3333.33"), D("3333.34")] and sum(amounts) == D("10000.00")
    assert pv["expense_allocations"][0]["method"] == "equal"


def test_the_typed_amount_plays_no_part_in_period_mode(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p3")
    assert head["default_amount"] == "1.00"
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    total = sum(D(l["amount"]) for l in _line_for(_preview(client, manager, cycle_id), head["name"]).values())
    assert total == D("4000.00")


# ── What counts as the period's expense ───────────────────────────────────────

def test_only_approved_live_spend_inside_the_period_counts(client, db):
    society, admin, manager, head, cycle_id, start, end = _setup(client, db, "p4")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())                     # counts
    _bill(client, admin, society.id, "housekeeping", "1000.00", start)                            # first day counts
    _bill(client, admin, society.id, "housekeeping", "700.00", end)                               # last day counts
    _bill(client, admin, society.id, "housekeeping", "9000.00", start - timedelta(days=1))        # before the period
    _bill(client, admin, society.id, "housekeeping", "9000.00", end + timedelta(days=1))          # after it
    _bill(client, admin, society.id, "housekeeping", "300.00", date.today())                      # will be pending
    _bill(client, admin, society.id, "housekeeping", "200.00", date.today())                      # will be cancelled
    _bill(client, admin, society.id, "housekeeping", "100.00", date.today())                      # will be reversed
    vouchers = {round(sum(e.debit for e in v.entries)): v for v in db.query(Voucher).filter_by(society_id=society.id)}
    vouchers[300].approval_status = "pending"
    vouchers[200].is_cancelled = True
    vouchers[100].reversed_at = datetime.utcnow()
    db.commit()
    pv = _preview(client, manager, cycle_id)
    alloc = pv["expense_allocations"][0]
    assert alloc["pool_amount"] == "5700.00"                                                      # 4000 + 1000 + 700
    assert alloc["pending_amount"] == "300.00"
    assert any("waiting for approval" in w and "300.00" in w for w in pv["warnings"])


def test_a_mirror_reversal_journal_does_not_add_to_the_pool(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p5")
    _bill(client, admin, society.id, "housekeeping", "2000.00", date.today())
    original = db.query(Voucher).filter_by(society_id=society.id).one()
    original.reversed_at = datetime.utcnow()
    mirror = Voucher(society_id=society.id, voucher_number="RV-1", voucher_type=original.voucher_type,
                     voucher_date=date.today(), fiscal_year=original.fiscal_year, amount=original.amount,
                     reversal_of_id=original.id, approval_status="approved")
    db.add(mirror); db.flush()
    from app.modules.accounts.models.accounts import VoucherEntry
    for e in original.entries:
        db.add(VoucherEntry(voucher_id=mirror.id, account_id=e.account_id, debit=e.credit, credit=e.debit))
    db.commit()
    pv = _preview(client, manager, cycle_id)
    assert pv["expense_allocations"] == []                                  # the void nets to nothing
    assert any("no approved expenses" in w for w in pv["warnings"])


def test_a_head_with_no_spend_in_the_period_bills_nothing_and_says_why(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p6")
    _bill(client, admin, society.id, "housekeeping", "5000.00", date.today() - timedelta(days=400))   # a year ago
    pv = _preview(client, manager, cycle_id)
    assert pv["flats"] == [] and pv["expense_allocations"] == []
    assert any(head["name"] in w and "nothing is billed" in w for w in pv["warnings"])


def test_spend_on_ledgers_no_element_covers_is_reported_not_billed(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p7")
    _bill(client, admin, society.id, "housekeeping", "3000.00", date.today())
    _bill(client, admin, society.id, "plumbing", "800.00", date.today())          # a ledger linked to no element
    pv = _preview(client, manager, cycle_id)
    assert pv["expense_allocations"][0]["pool_amount"] == "3000.00"
    assert any("no maintenance element covers" in w and "800.00" in w for w in pv["warnings"])


def test_another_societys_spend_never_enters_the_pool(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "p8")
    other, oadmin, omanager, _ = _rig(db, "p8b")
    _bill(client, admin, society.id, "housekeeping", "1000.00", date.today())
    _bill(client, oadmin, other.id, "housekeeping", "99999.00", date.today())
    assert _preview(client, manager, cycle_id)["expense_allocations"][0]["pool_amount"] == "1000.00"


# ── Generation keeps the working ──────────────────────────────────────────────

def test_generation_records_the_pool_the_vouchers_and_links_every_line(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "g1")
    _bill(client, admin, society.id, "housekeeping", "6000.00", date.today())
    _bill(client, admin, society.id, "housekeeping", "4000.01", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    alloc = db.query(BillingExpenseAllocation).filter_by(society_id=society.id).one()
    assert alloc.pool_amount == alloc.allocated_amount == D("10000.01")
    assert alloc.method == "area" and alloc.eligible_flats == 3 and alloc.charge_name == head["name"]
    assert alloc.total_weight == D("4000") and alloc.rate == D("2.5000025")
    assert sorted(s.amount for s in db.query(BillingExpenseSource).filter_by(allocation_id=alloc.id)) == \
        [D("4000.01"), D("6000.00")]
    lines = db.query(InvoiceLineItem).filter_by(allocation_id=alloc.id).all()
    assert len(lines) == 3 and sum(l.amount for l in lines) == D("10000.01")      # reconciles exactly


def test_a_later_charge_head_change_does_not_alter_issued_bills(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "g2")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager)
    before = sorted(l.amount for l in db.query(InvoiceLineItem).all() if l.allocation_id)
    _bill(client, admin, society.id, "housekeeping", "50000.00", date.today())      # booked after billing
    client.patch(f"{B}/charges/{head['id']}", json={"expense_mode": "trailing"}, headers=manager)
    db.expire_all()
    assert sorted(l.amount for l in db.query(InvoiceLineItem).all() if l.allocation_id) == before
    assert db.query(BillingExpenseAllocation).one().pool_amount == D("4000.00")


def test_the_same_expenses_cannot_be_billed_twice(client, db):
    society, admin, manager, head, cycle_id, start, end = _setup(client, db, "g3")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    overlapping = _cycle_dates(client, manager, society.id, end - timedelta(days=5), end + timedelta(days=25), "Overlap")
    pv = _preview(client, manager, overlapping)
    assert any("already billed" in w for w in pv["warnings"])
    r = client.post(f"{B}/cycles/{overlapping}/generate-bills", headers=manager)
    assert r.status_code == 409 and "already billed" in r.json()["detail"]
    assert db.query(MaintenanceBill).filter_by(cycle_id=UUID(overlapping)).count() == 0
    # a cycle that does not touch the period is fine
    later = _cycle_dates(client, manager, society.id, end + timedelta(days=1), end + timedelta(days=30), "Next")
    _bill(client, admin, society.id, "housekeeping", "900.00", end + timedelta(days=2))
    assert client.post(f"{B}/cycles/{later}/generate-bills", headers=manager).status_code == 200


def test_cancelling_every_bill_of_a_cycle_frees_its_period(client, db):
    society, admin, manager, head, cycle_id, start, end = _setup(client, db, "g4")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager)
    for bill in db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id)):
        bill.bill_status = BillStatus.CANCELLED
    db.commit()
    overlapping = _cycle_dates(client, manager, society.id, start, end, "Again")
    assert client.post(f"{B}/cycles/{overlapping}/generate-bills", headers=manager).status_code == 200


# ── The printed bill ──────────────────────────────────────────────────────────

def test_the_printed_bill_states_the_actual_expense_working_from_the_snapshot(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "b1")
    _bill(client, admin, society.id, "housekeeping", "10000.01", date.today())
    client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager)
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id)).join(MaintenanceBill.flat).filter_by(flat_number="201").one()
    _, text = _bill_pdf(db, bill.id)
    assert head["name"] in text and "actual expenses" in text
    assert "Rs. 10,000.01 in all" in text and "in proportion to flat area" in text and "3 flat(s)" in text
    assert "Your share: Rs. 5,000.01" in text
    assert "add up to exactly Rs. 10,000.01" in text


def test_a_bill_without_period_expenses_prints_no_statement(client, db):
    society, admin, manager, _ = _rig(db, "b2")
    _charge_from_element(client, manager, society.id, "housekeeping", basis="fixed", default_amount="450")
    today = date.today()
    cycle_id = _cycle_dates(client, manager, society.id, today, today + timedelta(days=30), "Plain")
    client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager)
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id)).first()
    _, text = _bill_pdf(db, bill.id)
    assert "actual expenses" not in text


# ── Setting the head up ───────────────────────────────────────────────────────

def test_period_mode_is_validated(client, db):
    society, admin, manager, _ = _rig(db, "v1")
    elements = client.get(f"{B}/elements/{society.id}", headers=manager).json()
    el = {e["code"]: e["id"] for e in elements}
    post = lambda **kw: client.post(f"{B}/charges", json={"society_id": str(society.id), **kw}, headers=manager)
    assert post(element_id=el["housekeeping"], expense_mode="monthly").status_code == 422        # unknown mode
    assert post(element_id=el["housekeeping"], expense_mode="period", auto_from_expenses=True,
                basis="parking").status_code == 422                                              # not an expense basis
    head = post(element_id=el["housekeeping"], basis="fixed", default_amount="1")
    assert head.status_code == 201 and head.json()["expense_mode"] == "trailing"                  # the default is unchanged
    ok = client.patch(f"{B}/charges/{head.json()['id']}",
                      json={"auto_from_expenses": True, "expense_mode": "period"}, headers=manager)
    assert ok.status_code == 200 and ok.json()["expense_mode"] == "period"
    assert client.patch(f"{B}/charges/{head.json()['id']}", json={"expense_mode": "x"}, headers=manager).status_code == 422
    assert client.patch(f"{B}/charges/{head.json()['id']}", json={"basis": "parking"}, headers=manager).status_code == 422


def test_two_heads_cannot_both_bill_one_elements_expenses(client, db):
    society, admin, manager, _ = _rig(db, "v2")
    first = _period_head(client, manager, society.id, basis="fixed")
    elements = {e["code"]: e["id"] for e in client.get(f"{B}/elements/{society.id}", headers=manager).json()}
    r = client.post(f"{B}/charges", json={
        "society_id": str(society.id), "element_id": elements["housekeeping"], "name": "Housekeeping 2",
        "auto_from_expenses": True, "basis": "per_sqft", "default_amount": "1"}, headers=manager)
    assert r.status_code == 422 and first["name"] in r.json()["detail"]
    second = client.post(f"{B}/charges", json={
        "society_id": str(society.id), "element_id": elements["housekeeping"], "name": "Housekeeping 2",
        "basis": "per_sqft", "default_amount": "1"}, headers=manager)
    assert second.status_code == 201                                       # fine while it does not bill from expenses
    r = client.patch(f"{B}/charges/{second.json()['id']}", json={"auto_from_expenses": True}, headers=manager)
    assert r.status_code == 422


# ── The trailing mode counts only approved, live spend ────────────────────────

def test_trailing_budgets_ignore_pending_and_reversed_spend(client, db):
    society, admin, manager, _ = _rig(db, "t1")
    _charge_from_element(client, manager, society.id, "housekeeping", basis="fixed", default_amount="1",
                         auto_from_expenses=True)
    _bill(client, admin, society.id, "housekeeping", "6000.00", date.today())
    _bill(client, admin, society.id, "housekeeping", "1500.00", date.today())
    pending = [v for v in db.query(Voucher).filter_by(society_id=society.id)
               if round(sum(e.debit for e in v.entries)) == 1500][0]
    pending.approval_status = "pending"
    db.commit()
    s = client.get(f"{B}/charges/{society.id}/budget-suggestions", headers=manager).json()["suggestions"][0]
    assert s["spent"] == "6000.00"
