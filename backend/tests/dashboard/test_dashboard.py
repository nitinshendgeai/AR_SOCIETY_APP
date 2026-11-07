"""The society dashboard: one call, scoped, admin/committee only."""
from datetime import date, datetime, timedelta

import pytest

from tests.conftest import make_flat, make_society, make_user, make_wing


def _admin(db, email, society):
    a = make_user(db, email, role="Society Admin")
    a["user"].society_id = society.id
    db.commit()
    return a


def _get(client, admin, society):
    return client.get(f"/api/v1/dashboard/society/{society.id}", headers=admin["headers"])


def _attention(body):
    return {i["key"]: i for i in body["attention"]}


def test_empty_society_has_every_block_and_nothing_to_attend_to(client, db):
    society = make_society(db, "Dash Empty")
    r = _get(client, _admin(db, "dash.empty@t.com", society), society)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"as_of", "collection", "money", "occupancy", "today", "staff", "attention", "errors"}
    assert body["collection"] is None                      # no billing cycle yet
    assert body["occupancy"] == {"flats": 0, "occupied": 0, "vacant": 0, "residents": 0}
    assert body["today"] == {"visitors_today": 0, "visitors_inside": 0}
    assert body["staff"] == {"active": 0}
    assert body["attention"] == []
    assert body["money"]["fy_income"] == "0"


def test_residents_and_other_societies_are_refused(client, db):
    society = make_society(db, "Dash Scope A")
    other = make_society(db, "Dash Scope B")
    resident = make_user(db, "dash.res@t.com", role="Resident")
    resident["user"].society_id = society.id
    db.commit()
    assert _get(client, resident, society).status_code == 403
    assert _get(client, _admin(db, "dash.a@t.com", society), other).status_code in (403, 404)


def test_occupancy_counts_flats_and_residents(client, db):
    from app.models.flat import OccupancyStatus
    from app.models.resident import Resident, ResidentType
    society = make_society(db, "Dash Occ")
    wing = make_wing(db, society.id, "W")
    f1, f2, _ = (make_flat(db, wing.id, n) for n in ("1", "2", "3"))
    f1.occupancy_status = OccupancyStatus.OWNER_OCCUPIED
    f2.occupancy_status = OccupancyStatus.TENANT_OCCUPIED
    db.add(Resident(flat_id=f1.id, full_name="Owner One", resident_type=ResidentType.OWNER, is_primary=True))
    db.commit()
    body = _get(client, _admin(db, "dash.occ@t.com", society), society).json()
    assert body["occupancy"] == {"flats": 3, "occupied": 2, "vacant": 1, "residents": 1}


def test_attention_items_are_counted_and_ranked(client, db):
    from app.models.agreement_tracker import AgreementStatus, AgreementTracker
    from app.models.password_reset_request import PasswordResetRequest
    from app.models.tenant import Tenant
    from app.modules.complaint.models.complaint import Complaint, ComplaintCategory

    society = make_society(db, "Dash Attention")
    admin = _admin(db, "dash.att@t.com", society)
    wing = make_wing(db, society.id, "W")
    flat = make_flat(db, wing.id, "1")

    old = Complaint(society_id=society.id, complaint_number="C-1", title="Leak", description="d",
                    category=list(ComplaintCategory)[0], raised_by=admin["user"].id)
    old.created_at = datetime.utcnow() - timedelta(days=10)
    fresh = Complaint(society_id=society.id, complaint_number="C-2", title="Light", description="d",
                      category=list(ComplaintCategory)[0], raised_by=admin["user"].id)
    db.add_all([old, fresh])

    tenant = Tenant(flat_id=flat.id, full_name="T One")
    db.add(tenant); db.flush()
    db.add(AgreementTracker(society_id=society.id, flat_id=flat.id, tenant_id=tenant.id,
                            start_date=date.today() - timedelta(days=400),
                            end_date=date.today() - timedelta(days=3), status=AgreementStatus.ACTIVE))
    db.add(PasswordResetRequest(user_id=admin["user"].id, society_id=society.id, identifier="x"))
    db.commit()

    body = _get(client, admin, society).json()
    items = _attention(body)
    assert items["complaints_old"]["count"] == 1 and items["complaints_old"]["severity"] == "high"
    assert items["complaints_open"]["count"] == 2
    assert items["agreements_expired"]["count"] == 1
    assert items["password_resets"]["count"] == 1
    # ranked: high before medium before info
    rank = {"high": 0, "medium": 1, "info": 2}
    assert [rank[i["severity"]] for i in body["attention"]] == sorted(rank[i["severity"]] for i in body["attention"])


def test_a_failing_block_does_not_blank_the_page(client, db, monkeypatch):
    from app.modules.dashboard.services import dashboard_service as ds
    society = make_society(db, "Dash Fail")
    admin = _admin(db, "dash.fail@t.com", society)
    monkeypatch.setattr(ds.DashboardService, "_money_block", lambda self, sid, today: 1 / 0)
    r = _get(client, admin, society)
    assert r.status_code == 200
    assert r.json()["money"] is None
    assert r.json()["occupancy"] is not None
    assert r.json()["errors"] == ["money"]      # the app is told this is a failure, not "no data"


def test_a_failing_attention_block_is_reported_not_shown_as_all_clear(client, db, monkeypatch):
    from app.modules.dashboard.services import dashboard_service as ds
    society = make_society(db, "Dash Attn Fail")
    admin = _admin(db, "dash.attn@t.com", society)
    monkeypatch.setattr(ds.DashboardService, "_attention", lambda self, sid, today: 1 / 0)
    body = _get(client, admin, society).json()
    assert body["attention"] == []
    assert "attention" in body["errors"]


def test_a_failing_collection_block_is_reported(client, db, monkeypatch):
    from app.modules.dashboard.services import dashboard_service as ds
    society = make_society(db, "Dash Coll Fail")
    admin = _admin(db, "dash.coll@t.com", society)
    monkeypatch.setattr(ds.DashboardService, "_collection", lambda self, sid, today: 1 / 0)
    body = _get(client, admin, society).json()
    assert body["collection"] is None
    # The service rolls back after a failed block; in this test's single outer transaction that also drops the
    # society row, so later blocks may fail too. What matters here is that the failure is named.
    assert "collection" in body["errors"]


def test_no_errors_when_every_block_loads(client, db):
    society = make_society(db, "Dash No Err")
    admin = _admin(db, "dash.noerr@t.com", society)
    assert _get(client, admin, society).json()["errors"] == []


# ── The gate's own summary: GET /dashboard/security/{society_id} ─────────────────

def _sec(db, email, society, role="Security Staff"):
    u = make_user(db, email, role=role)
    u["user"].society_id = society.id
    db.commit()
    return u


def _gate(client, who, society):
    return client.get(f"/api/v1/dashboard/security/{society.id}", headers=who["headers"])


def _visitor(db, society, name, status="pending", created=None, checked_in=None):
    from app.modules.visitor.models.visitor import Visitor, VisitorStatus
    v = Visitor(name=name, mobile="9000000000", society_id=society.id, status=VisitorStatus(status))
    if created:
        v.created_at = created
    if checked_in:
        v.checked_in_at = checked_in
    db.add(v)
    db.commit()
    return v


def test_security_staff_see_todays_gate_figures(client, db):
    society = make_society(db, "Gate Counts")
    guard = _sec(db, "gate.guard@t.com", society)
    now = datetime.utcnow()
    _visitor(db, society, "In now", status="checked_in", checked_in=now)
    _visitor(db, society, "Came and left", status="checked_out", checked_in=now)
    _visitor(db, society, "Waiting", status="pending")
    _visitor(db, society, "Yesterday", status="checked_out", created=now - timedelta(days=2),
             checked_in=now - timedelta(days=2))
    r = _gate(client, guard, society)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["today"] == {"visitors_today": 3, "checked_in_today": 2, "visitors_inside": 1}
    assert body["errors"] == []
    assert set(body) == {"as_of", "today", "errors"}      # nothing about money, people or other modules


def test_a_quiet_gate_is_zero_not_missing(client, db):
    society = make_society(db, "Gate Quiet")
    guard = _sec(db, "gate.quiet@t.com", society)
    assert _gate(client, guard, society).json()["today"] == {
        "visitors_today": 0, "checked_in_today": 0, "visitors_inside": 0}


def test_gate_summary_roles(client, db):
    """The same people who can read the visitor log; nobody else."""
    society = make_society(db, "Gate Roles")
    allowed = ["Society Admin", "Committee Member", "Manager", "Security Supervisor", "Security Staff"]
    for i, role in enumerate(allowed):
        assert _gate(client, _sec(db, f"gate.ok{i}@t.com", society, role), society).status_code == 200, role
    refused = ["Resident", "Tenant", "Housekeeping Staff", "Technical Supervisor"]
    for i, role in enumerate(refused):
        who = _sec(db, f"gate.no{i}@t.com", society, role)
        assert _gate(client, who, society).status_code == 403, role


def test_gate_summary_needs_a_login(client, db):
    society = make_society(db, "Gate Anon")
    assert client.get(f"/api/v1/dashboard/security/{society.id}").status_code in (401, 403)


def test_gate_summary_is_scoped_to_the_callers_society(client, db):
    mine = make_society(db, "Gate Mine")
    other = make_society(db, "Gate Other")
    guard = _sec(db, "gate.scope@t.com", mine)
    _visitor(db, other, "Not mine", status="checked_in", checked_in=datetime.utcnow())
    assert _gate(client, guard, other).status_code == 403             # another society's gate is refused
    assert _gate(client, guard, mine).json()["today"]["visitors_inside"] == 0   # and its visitors never counted


def test_gate_summary_follows_the_visitors_switch(client, db):
    from app.models.society_service import SocietyService
    society = make_society(db, "Gate Switch")
    guard = _sec(db, "gate.switch@t.com", society)
    db.add(SocietyService(society_id=society.id, service_key="visitors", enabled=False))
    db.commit()
    body = _gate(client, guard, society).json()
    assert body["today"] is None and body["errors"] == []


def test_a_failing_gate_block_is_reported(client, db, monkeypatch):
    from app.modules.dashboard.services import dashboard_service as ds
    society = make_society(db, "Gate Fail")
    guard = _sec(db, "gate.fail@t.com", society)
    monkeypatch.setattr(ds.DashboardService, "_gate_today", lambda self, sid, tz: 1 / 0)
    body = _gate(client, guard, society).json()
    assert body["today"] is None
    assert body["errors"] == ["today"]


# ── The figures are the ones on the screens they lead to ─────────────────────────────────────────────

def _staff(db, society, n, active=True):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    s = Staff(society_id=society.id, employee_code=f"D{society.id.hex[:4]}{n}", full_name=f"Staff {n}",
              mobile=f"97{n:08d}", department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE, is_active=active)
    db.add(s)
    return s


def test_active_staff_is_every_active_member_not_one_page(client, db):
    """The staff list is paged (50 a page), so counting what it returned stopped at 50."""
    society = make_society(db, "Dash Staff")
    admin = _admin(db, "dash.staff@t.com", society)
    for n in range(55):
        _staff(db, society, n)
    _staff(db, society, 900, active=False)      # left; not counted
    db.commit()
    assert _get(client, admin, society).json()["staff"] == {"active": 55}


def test_defaulters_and_members_owe_match_the_defaulters_screen(client, db):
    """The "defaulters" row and the "Members owe" card show the Defaulters screen's own totals."""
    from decimal import Decimal
    from tests.billing.test_defaulters import _two_cycles
    society, _f1, _f2, manager, _res = _two_cycles(client, db, "dsh1")
    screen = client.get(f"/api/v1/billing/defaulters/{society.id}", headers=manager["headers"]).json()["summary"]
    assert screen["defaulters"] == 1 and screen["flats_with_dues"] == 2         # the rig: one over 3 months, one under

    admin = _admin(db, "dash.dues@t.com", society)
    body = _get(client, admin, society).json()
    row = _attention(body)["overdue_bills"]
    assert row["count"] == screen["defaulters"]
    assert Decimal(row["amount"]) == Decimal(screen["defaulters_outstanding"])
    assert row["months"] == screen["min_months"] == 3
    assert Decimal(body["money"]["members_dues"]) == Decimal(screen["total_outstanding"])


def test_open_complaints_mean_the_same_everywhere(client, db):
    """Open, assigned, in progress and reopened are open; resolved, closed, rejected and deleted ones are not. The
    admin dashboard and the manager's count agree."""
    from app.modules.complaint.models.complaint import Complaint, ComplaintCategory, ComplaintStatus
    society = make_society(db, "Dash Open")
    admin = _admin(db, "dash.open@t.com", society)
    manager = make_user(db, "dash.open.mgr@t.com", role="Manager")
    manager["user"].society_id = society.id
    for n, status in enumerate(ComplaintStatus):
        db.add(Complaint(society_id=society.id, complaint_number=f"O-{n}", title=status.value, description="d",
                         category=list(ComplaintCategory)[0], raised_by=admin["user"].id, status=status))
    db.add(Complaint(society_id=society.id, complaint_number="O-X", title="deleted", description="d",
                     category=list(ComplaintCategory)[0], raised_by=admin["user"].id,
                     status=ComplaintStatus.OPEN, is_active=False))
    db.commit()

    on_dashboard = _attention(_get(client, admin, society).json())["complaints_open"]["count"]
    r = client.get(f"/api/v1/complaints/society/{society.id}/open-count", headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert on_dashboard == r.json()["open"] == 4


def test_open_complaint_count_is_refused_to_residents_and_other_societies(client, db):
    society = make_society(db, "Dash Open Scope")
    other = make_society(db, "Dash Open Scope B")
    resident = make_user(db, "dash.open.res@t.com", role="Resident")
    resident["user"].society_id = society.id
    manager = make_user(db, "dash.open.m2@t.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()
    assert client.get(f"/api/v1/complaints/society/{society.id}/open-count", headers=resident["headers"]).status_code == 403
    assert client.get(f"/api/v1/complaints/society/{other.id}/open-count", headers=manager["headers"]).status_code in (403, 404)


def test_punches_waiting_include_punch_outs(client, db):
    """The row leads to the Approvals screen, which lists punch-ins and punch-outs awaiting approval."""
    from app.modules.staff.models.staff import StaffAttendance
    society = make_society(db, "Dash Punch")
    admin = _admin(db, "dash.punch@t.com", society)
    a, b = _staff(db, society, 1), _staff(db, society, 2)
    db.flush()
    today = date.today()
    db.add(StaffAttendance(society_id=society.id, staff_id=a.id, attendance_date=today,
                           check_in_time=datetime.utcnow(), is_approved=False))
    db.add(StaffAttendance(society_id=society.id, staff_id=b.id, attendance_date=today,
                           check_in_time=datetime.utcnow(), check_out_time=datetime.utcnow(),
                           is_approved=True, is_checkout_approved=False))
    db.commit()
    assert _attention(_get(client, admin, society).json())["punch_approvals"]["count"] == 2


def test_collection_percent_never_rounds_up_to_a_full_100(client, db):
    from decimal import Decimal
    from app.modules.billing.models.billing import MaintenanceBill
    from tests.billing.test_maintenance_billing import _charge, _cycle, _rig
    society, flat1, flat2, manager, _r, _o = _rig(db, "dsh2")
    h = manager["headers"]
    _charge(client, h, society.id, amount="1000.00")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    bill = db.query(MaintenanceBill).filter_by(flat_id=flat1.id).one()
    other = db.query(MaintenanceBill).filter_by(flat_id=flat2.id).one()
    bill.paid_amount = bill.total_amount
    other.paid_amount = other.total_amount - Decimal("1.00")            # one rupee short: 99.95%
    db.commit()
    admin = _admin(db, "dash.pct@t.com", society)
    c = _get(client, admin, society).json()["collection"]
    assert Decimal(c["outstanding"]) > 0 and c["percent"] == 99


def test_collection_counts_issued_bills_only(client, db):
    """Bills made but not yet sent to residents are owed by nobody: they are not "billed" or "outstanding" on the
    dashboard, and the card says how many are waiting to be issued."""
    from decimal import Decimal
    from tests.billing.test_maintenance_billing import _charge, _cycle, _rig
    society, _f1, _f2, manager, _r, _o = _rig(db, "dsh3")
    h = manager["headers"]
    _charge(client, h, society.id, amount="1000.00")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    admin = _admin(db, "dash.draft@t.com", society)

    drafts = _get(client, admin, society).json()["collection"]
    assert Decimal(drafts["billed"]) == 0 and Decimal(drafts["outstanding"]) == 0
    assert drafts["bills"] == 0 and drafts["draft_bills"] == 2
    cycle = client.get(f"/api/v1/billing/cycles/detail/{cycle_id}", headers=h).json()
    assert Decimal(cycle["total_billed"]) > 0                    # the cycle itself still shows the preview
    assert Decimal(cycle["issued_billed"]) == 0

    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    issued = _get(client, admin, society).json()["collection"]
    assert Decimal(issued["billed"]) == Decimal(cycle["total_billed"])
    assert Decimal(issued["outstanding"]) == Decimal(cycle["total_billed"])
    assert issued["bills"] == 2 and issued["draft_bills"] == 0


def test_my_open_complaints_count_is_not_limited_to_the_newest_page(client, db):
    from app.modules.complaint.models.complaint import Complaint, ComplaintCategory, ComplaintStatus
    society = make_society(db, "Dash My Open")
    resident = make_user(db, "dash.myopen@t.com", role="Resident")
    resident["user"].society_id = society.id
    other = make_user(db, "dash.myopen2@t.com", role="Resident")
    other["user"].society_id = society.id
    db.commit()
    cat = list(ComplaintCategory)[0]
    for n in range(55):
        db.add(Complaint(society_id=society.id, complaint_number=f"M-{n}", title="t", description="d", category=cat,
                         raised_by=resident["user"].id, status=ComplaintStatus.OPEN))
    db.add(Complaint(society_id=society.id, complaint_number="M-R", title="t", description="d", category=cat,
                     raised_by=resident["user"].id, status=ComplaintStatus.RESOLVED))
    db.add(Complaint(society_id=society.id, complaint_number="M-O", title="t", description="d", category=cat,
                     raised_by=other["user"].id, status=ComplaintStatus.OPEN))
    db.commit()
    r = client.get("/api/v1/complaints/me/open-count", headers=resident["headers"])
    assert r.status_code == 200, r.text
    assert r.json() == {"open": 55}                              # past the 50 of one page; not resolved, not someone else's
