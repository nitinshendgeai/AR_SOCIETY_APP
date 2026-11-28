"""Correcting a billing cycle made under the wrong month: its name and period, with the bills' periods moving along so the
next cycle bills from the right day."""
from datetime import date
from uuid import UUID

from app.modules.billing.models.billing import MaintenanceBill
from tests.billing.test_maintenance_billing import _charge, _cycle, _generated_cycle, _rig

B = "/api/v1/billing"


def _patch(client, h, cycle_id, **body):
    return client.patch(f"{B}/cycles/{cycle_id}", json=body, headers=h)


def test_the_name_can_be_changed_at_any_time(client, db):
    society, _f1, _f2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "uc1")
    h = manager["headers"]
    r = _patch(client, h, cycle_id, name="  September 2026 Maintenance ")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "September 2026 Maintenance"
    assert _patch(client, h, cycle_id, name="   ").status_code == 422
    assert _patch(client, h, cycle_id, name=None).json()["name"] == "September 2026 Maintenance"   # null: unchanged


def test_issued_bills_move_to_the_corrected_period_and_the_next_cycle_bills_from_there(client, db):
    society, flat1, _f2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "uc2")
    h = manager["headers"]
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    # the dates cannot move while bills are unissued, but these are issued
    r = _patch(client, h, cycle_id, name="September 2026 Maintenance",
               cycle_start="2026-09-01", cycle_end="2026-09-30")
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["cycle_start"], body["cycle_end"]) == ("2026-09-01", "2026-09-30")
    assert body["bills_period_moved"] == 2 and body["bills_with_own_period"] == 0
    db.expire_all()
    for b in db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id)):
        assert b.period_start in (None, date(2026, 9, 1)) and b.period_end in (None, date(2026, 9, 30))
    assert _patch(client, h, cycle_id, cycle_start="2026-10-05", cycle_end="2026-10-01").status_code == 422


def test_dates_are_not_changed_under_unissued_bills_and_only_managers_edit(client, db):
    society, _f1, _f2, manager, resident, _o, cycle_id = _generated_cycle(client, db, "uc3")
    h = manager["headers"]
    r = _patch(client, h, cycle_id, cycle_start="2026-09-01", cycle_end="2026-09-30")
    assert r.status_code == 409 and "regenerate" in r.json()["detail"]
    assert _patch(client, resident["headers"], cycle_id, name="X").status_code == 403
    cycles = {c["id"]: c for c in client.get(f"{B}/cycles/{society.id}", headers=h).json()}
    assert cycles[cycle_id]["cycle_start"] != "2026-09-01"
