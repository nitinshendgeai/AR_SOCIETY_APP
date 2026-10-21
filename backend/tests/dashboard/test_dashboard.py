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
    assert set(body) == {"as_of", "collection", "money", "occupancy", "today", "attention", "errors"}
    assert body["collection"] is None                      # no billing cycle yet
    assert body["occupancy"] == {"flats": 0, "occupied": 0, "vacant": 0, "residents": 0}
    assert body["today"] == {"visitors_today": 0, "visitors_inside": 0}
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
    monkeypatch.setattr(ds.DashboardService, "_money_block", lambda self, sid: 1 / 0)
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
    monkeypatch.setattr(ds.DashboardService, "_collection", lambda self, sid: 1 / 0)
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
