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
    assert set(body) == {"as_of", "collection", "money", "occupancy", "today", "attention"}
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
