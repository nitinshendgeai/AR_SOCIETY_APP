"""The platform console: a suspended society is really shut, the society list carries usage and filters, one society's
detail, limits, and the record of what platform admins did."""
from datetime import date, timedelta

import pytest

from app.core.security import hash_password
from app.models.society import AccountStatus
from tests.conftest import make_flat, make_user, make_wing
from tests.platform_admin.test_platform_admin import make_superadmin, make_trial_society

P = "/api/v1/platform-admin"


def _member(db, society, email, role="Society Admin", name=None):
    who = make_user(db, email, role=role, full_name=name or email.split("@")[0])
    who["user"].society_id = society.id
    who["user"].hashed_password = hash_password("Test@1234")
    db.commit()
    return who


@pytest.fixture
def two(db):
    a = make_trial_society(db, "Shut Society", "SHT01")
    b = make_trial_society(db, "Open Society", "OPN01")
    return {"a": a, "b": b,
            "admin_a": _member(db, a, "admin@shut.test", name="Asha Admin"),
            "admin_b": _member(db, b, "admin@open.test", name="Omkar Open")}


# ── Suspension is enforced ────────────────────────────────────────────────────

def _suspend(client, db, society, reason="Unpaid"):
    _, h = make_superadmin(db)
    r = client.post(f"{P}/societies/{society.id}/suspend", json={"reason": reason}, headers=h)
    assert r.status_code == 200, r.text
    return h


def test_a_suspended_society_cannot_use_the_api(client, db, two):
    ok = client.get("/api/v1/societies/", headers=two["admin_a"]["headers"])
    assert ok.status_code != 403
    _suspend(client, db, two["a"])
    r = client.get("/api/v1/societies/", headers=two["admin_a"]["headers"])
    assert r.status_code == 403 and "suspended" in r.json()["detail"]
    # the other society carries on
    assert client.get("/api/v1/societies/", headers=two["admin_b"]["headers"]).status_code != 403


def test_a_suspended_user_can_still_learn_who_they_are_and_sign_out(client, db, two):
    _suspend(client, db, two["a"])
    h = two["admin_a"]["headers"]
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=h).status_code in (200, 204)


def test_a_suspended_society_cannot_sign_in(client, db, two):
    _suspend(client, db, two["a"])
    r = client.post("/api/v1/auth/login", json={"email": "admin@shut.test", "password": "Test@1234"})
    assert r.status_code == 403 and "suspended" in r.json()["detail"]
    r = client.post("/api/v1/auth/login", json={"email": "admin@open.test", "password": "Test@1234"})
    assert r.status_code == 200


def test_reactivating_lets_them_back_in(client, db, two):
    h = _suspend(client, db, two["a"])
    assert client.post(f"{P}/societies/{two['a'].id}/activate", json={"plan": "starter"}, headers=h).status_code == 200
    assert client.get("/api/v1/societies/", headers=two["admin_a"]["headers"]).status_code != 403
    assert client.post("/api/v1/auth/login", json={"email": "admin@shut.test", "password": "Test@1234"}).status_code == 200


def test_the_platform_admin_is_never_locked_out(client, db, two):
    h = _suspend(client, db, two["a"])
    assert client.get(f"{P}/stats", headers=h).status_code == 200


def test_an_ended_trial_is_flagged_but_not_blocked(client, db, two):
    two["a"].trial_end_date = date.today() - timedelta(days=5)
    db.commit()
    assert client.get("/api/v1/societies/", headers=two["admin_a"]["headers"]).status_code != 403
    _, h = make_superadmin(db)
    row = [s for s in client.get(f"{P}/societies", headers=h).json() if s["id"] == str(two["a"].id)][0]
    assert row["trial_ended"] is True and row["account_status"] == "TRIAL" and row["trial_days_remaining"] == 0


def test_suspending_needs_a_reason(client, db, two):
    _, h = make_superadmin(db)
    assert client.post(f"{P}/societies/{two['a'].id}/suspend", json={"reason": "   "}, headers=h).status_code == 422
    assert client.post(f"{P}/societies/{two['a'].id}/suspend", json={}, headers=h).status_code == 422


# ── List, detail, limits, activity ────────────────────────────────────────────

def test_the_list_carries_usage_filters_and_search(client, db, two):
    wing = make_wing(db, two["a"].id)
    make_flat(db, wing.id, "101"); make_flat(db, wing.id, "102")
    _, h = make_superadmin(db)
    rows = {s["name"]: s for s in client.get(f"{P}/societies", headers=h).json()}
    a = rows["Shut Society"]
    assert a["user_count"] == 1 and a["flat_count"] == 2 and a["allowed_users"] == 50
    assert rows["Open Society"]["flat_count"] == 0
    assert [s["name"] for s in client.get(f"{P}/societies", params={"q": "shut"}, headers=h).json()] == ["Shut Society"]
    assert [s["name"] for s in client.get(f"{P}/societies", params={"q": "OPN01"}, headers=h).json()] == ["Open Society"]
    two["b"].account_status = AccountStatus.ACTIVE
    db.commit()
    names = [s["name"] for s in client.get(f"{P}/societies", params={"status": "active"}, headers=h).json()]
    assert names == ["Open Society"]
    assert client.get(f"{P}/societies", params={"status": "nonsense"}, headers=h).status_code == 422


def test_society_detail_shows_admins_usage_and_history(client, db, two):
    h = _suspend(client, db, two["a"], reason="Chargeback")
    d = client.get(f"{P}/societies/{two['a'].id}", headers=h).json()
    assert d["name"] == "Shut Society" and d["account_status"] == "SUSPENDED"
    assert [a["name"] for a in d["admins"]] == ["Asha Admin"] and d["admins"][0]["email"] == "admin@shut.test"
    assert d["history"][0]["event"] == "society_suspended" and d["history"][0]["details"]["reason"] == "Chargeback"
    assert d["history"][0]["by"] == "Platform Admin"
    assert client.get(f"{P}/societies/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404


def test_limits_are_validated_and_not_below_usage(client, db, two):
    _, h = make_superadmin(db)
    _member(db, two["a"], "res1@shut.test", "Resident"); _member(db, two["a"], "res2@shut.test", "Resident")
    url = f"{P}/societies/{two['a'].id}/limits"
    assert client.put(url, json={"allowed_users": 0, "allowed_flats": 10, "allowed_storage_mb": 100}, headers=h).status_code == 422
    low = client.put(url, json={"allowed_users": 2, "allowed_flats": 10, "allowed_storage_mb": 100}, headers=h)
    assert low.status_code == 409 and "3 users" in low.json()["detail"]
    ok = client.put(url, json={"allowed_users": 200, "allowed_flats": 400, "allowed_storage_mb": 2048}, headers=h)
    assert ok.status_code == 200
    d = client.get(f"{P}/societies/{two['a'].id}", headers=h).json()
    assert d["allowed_users"] == 200 and d["allowed_flats"] == 400 and d["allowed_storage_mb"] == 2048
    assert d["history"][0]["event"] == "limits_changed"


def test_activation_can_record_when_the_paid_period_ends(client, db, two):
    _, h = make_superadmin(db)
    url = f"{P}/societies/{two['a'].id}/activate"
    assert client.post(url, json={"plan": "growth", "expires_on": str(date.today() - timedelta(days=1))}, headers=h).status_code == 422
    end = date.today() + timedelta(days=365)
    assert client.post(url, json={"plan": "growth", "expires_on": str(end)}, headers=h).status_code == 200
    d = client.get(f"{P}/societies/{two['a'].id}", headers=h).json()
    assert d["subscription_plan"] == "growth" and d["subscription_expiry_date"] == str(end) and d["account_status"] == "ACTIVE"


def test_activity_lists_what_was_done_across_societies(client, db, two):
    h = _suspend(client, db, two["a"])
    client.post(f"{P}/societies/{two['b'].id}/extend-trial", json={"extend_days": 10}, headers=h)
    rows = client.get(f"{P}/activity", headers=h).json()
    events = [(r["event"], r["society_name"]) for r in rows]
    assert ("society_suspended", "Shut Society") in events and ("trial_extended", "Open Society") in events


def test_stats_include_totals_and_unmarked_ended_trials(client, db, two):
    two["b"].trial_end_date = date.today() - timedelta(days=2)
    db.commit()
    _, h = make_superadmin(db)
    s = client.get(f"{P}/stats", headers=h).json()
    assert s["total_users"] >= 2 and s["trial_ended_not_marked"] >= 1


def test_only_a_platform_admin_may_use_any_of_it(client, db, two):
    h = two["admin_a"]["headers"]
    for method, path, body in [
        ("get", f"{P}/societies", None), ("get", f"{P}/societies/{two['a'].id}", None), ("get", f"{P}/activity", None),
        ("put", f"{P}/societies/{two['a'].id}/limits", {"allowed_users": 5, "allowed_flats": 5, "allowed_storage_mb": 5}),
    ]:
        r = getattr(client, method)(path, headers=h, **({"json": body} if body else {}))
        assert r.status_code == 403, (method, path)
