"""Automatic tasks: run once per period, tell the right people, respect the switches."""
from datetime import date, datetime, timedelta

from app.models.agreement_tracker import AgreementStatus, AgreementTracker
from app.models.notification import Notification
from app.models.tenant import Tenant
from app.modules.automation.models.automation import ScheduledJobRun
from app.modules.automation.services.automation_service import AutomationService
from app.modules.visitor.models.visitor import Visitor, VisitorStatus
from tests.conftest import make_flat, make_society, make_user, make_wing


def _admin(db, email, society):
    a = make_user(db, email, role="Society Admin")
    a["user"].society_id = society.id
    db.commit()
    return a


def _notes(db, user, module=None):
    q = db.query(Notification).filter(Notification.user_id == user["user"].id)
    return q.filter(Notification.module == module).all() if module else q.all()


def test_agreement_alert_goes_to_the_office_once_per_stage(db):
    society = make_society(db, "Auto Agr")
    admin = _admin(db, "auto.agr@t.com", society)
    wing = make_wing(db, society.id, "W")
    flat = make_flat(db, wing.id, "101")
    tenant = Tenant(flat_id=flat.id, full_name="Tina Tenant")
    db.add(tenant); db.flush()
    agr = AgreementTracker(society_id=society.id, flat_id=flat.id, tenant_id=tenant.id,
                           start_date=date.today() - timedelta(days=300),
                           end_date=date.today() + timedelta(days=20), status=AgreementStatus.ACTIVE)
    db.add(agr); db.commit()

    svc = AutomationService(db)
    run = svc.run_job(society.id, "agreement_alerts", today=date.today())
    assert run.status == "ok" and "1 agreement alert" in run.summary
    assert len(_notes(db, admin, "agreement")) == 1
    assert "Tina Tenant" in _notes(db, admin, "agreement")[0].body

    # the same day again does nothing; a manual run finds nothing new to say (30-day alert already sent)
    assert svc.run_job(society.id, "agreement_alerts", today=date.today()) is None
    run2 = svc.run_job(society.id, "agreement_alerts", manual=True)
    assert "0 agreement alert" in run2.summary
    assert len(_notes(db, admin, "agreement")) == 1

    # inside 7 days the second alert goes out
    agr.end_date = date.today() + timedelta(days=5); db.commit()
    run3 = svc.run_job(society.id, "agreement_alerts", manual=True)
    assert "1 agreement alert" in run3.summary
    assert len(_notes(db, admin, "agreement")) == 2


def test_one_run_per_period_and_it_is_logged(db):
    society = make_society(db, "Auto Period")
    _admin(db, "auto.per@t.com", society)
    svc = AutomationService(db)
    first = svc.run_job(society.id, "visitor_expiry")
    again = svc.run_job(society.id, "visitor_expiry")
    assert first is not None and again is None
    rows = db.query(ScheduledJobRun).filter(ScheduledJobRun.society_id == society.id).all()
    assert len(rows) == 1 and rows[0].status == "ok" and rows[0].finished_at is not None


def test_unanswered_visitor_requests_expire_after_a_day(db):
    society = make_society(db, "Auto Visitors")
    old = Visitor(society_id=society.id, name="Old", mobile="9000000001", purpose="x", status=VisitorStatus.PENDING)
    new = Visitor(society_id=society.id, name="New", mobile="9000000002", purpose="x", status=VisitorStatus.PENDING)
    db.add_all([old, new]); db.flush()
    old.created_at = datetime.utcnow() - timedelta(hours=30)
    db.commit()
    run = AutomationService(db).run_job(society.id, "visitor_expiry")
    assert "1 request" in run.summary
    db.refresh(old); db.refresh(new)
    assert old.status == VisitorStatus.EXPIRED and new.status == VisitorStatus.PENDING


def test_run_due_respects_switches_and_the_run_hour(db):
    society = make_society(db, "Auto Due")
    _admin(db, "auto.due@t.com", society)
    svc = AutomationService(db)
    svc.update_settings(society.id, {"agreement_alerts": False, "asset_alerts": False, "billing_nudge": False})
    # 02:00 UTC is 07:30 in India: too early, nothing runs
    assert svc.run_due(now=datetime(2026, 10, 9, 2, 0)) == 0
    # 04:00 UTC is 09:30 in India: only the visitor task is on
    ran = svc.run_due(now=datetime(2026, 10, 9, 4, 0))
    jobs = {r.job for r in db.query(ScheduledJobRun).filter(ScheduledJobRun.society_id == society.id)}
    assert ran == 1 and jobs == {"visitor_expiry"}
    # dues reminders to members stay off unless switched on
    assert "dues_reminders" not in jobs


def test_a_failing_task_is_recorded_not_raised(db, monkeypatch):
    society = make_society(db, "Auto Fail")
    svc = AutomationService(db)
    monkeypatch.setattr(AutomationService, "_job_visitor_expiry", lambda self, *a: 1 / 0)
    run = svc.run_job(society.id, "visitor_expiry")
    assert run.status == "error" and "ZeroDivisionError" in run.summary


def test_settings_endpoint_roles_scope_and_run_now(client, db):
    society = make_society(db, "Auto Api")
    other = make_society(db, "Auto Api B")
    admin = _admin(db, "auto.api@t.com", society)
    resident = make_user(db, "auto.res@t.com", role="Resident")
    resident["user"].society_id = society.id
    db.commit()
    base = f"/api/v1/automation/{society.id}"

    assert client.get(base, headers=resident["headers"]).status_code == 403
    assert client.get(f"/api/v1/automation/{other.id}", headers=admin["headers"]).status_code in (403, 404)

    body = client.get(base, headers=admin["headers"]).json()
    assert body["settings"]["dues_reminders"] is False and body["settings"]["agreement_alerts"] is True
    assert {j["key"] for j in body["jobs"]} == {"dues_reminders", "agreement_alerts", "asset_alerts",
                                                "billing_nudge", "visitor_expiry"}

    changed = client.put(base, json={"dues_reminders": True, "reminder_every_days": 14},
                         headers=admin["headers"]).json()
    assert changed["settings"]["dues_reminders"] is True and changed["settings"]["reminder_every_days"] == 14
    assert client.put(base, json={"reminder_every_days": 0}, headers=admin["headers"]).status_code == 422

    r = client.post(f"{base}/run", json={"job": "visitor_expiry"}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["status"] == "ok"
    last = [j for j in client.get(base, headers=admin["headers"]).json()["jobs"] if j["key"] == "visitor_expiry"][0]
    assert last["last_run"]["manual"] is True
    assert client.post(f"{base}/run", json={"job": "nope"}, headers=admin["headers"]).status_code == 422


def test_dues_reminder_task_passes_the_society_settings_through(db, monkeypatch):
    from app.modules.billing.services.defaulters import MemberDues
    society = make_society(db, "Auto Dues")
    svc = AutomationService(db)
    svc.update_settings(society.id, {"dues_reminders": True, "reminder_every_days": 10, "reminder_min_months": 2})
    seen = {}

    def fake(self, society_id, flat_ids, min_months, user, not_reminded_within_days=None):
        seen.update(flat_ids=flat_ids, min_months=min_months, user=user, within=not_reminded_within_days)
        return {"flats_reminded": 3, "notifications": 4, "flats_without_app_login": ["A-1"]}

    monkeypatch.setattr(MemberDues, "remind", fake)
    run = svc.run_job(society.id, "dues_reminders")
    assert seen == {"flat_ids": None, "min_months": 2, "user": None, "within": 10}
    assert run.summary == "Reminded 3 flat(s); 1 had nobody with an app login"
