"""The platform owner switches optional services on or off for one society by hand: an off service is closed in the
API and hidden from the menu, the core never is, and other societies are untouched."""
from app.core.society_gate import service_block_reason
from tests.platform_admin.test_platform_admin import make_superadmin
from tests.platform_admin.test_platform_console import P, _member, two  # noqa: F401

API = "/api/v1"


def _switch(client, h, society, key, enabled):
    return client.put(f"{P}/societies/{society.id}/services/{key}", json={"enabled": enabled}, headers=h)


def _states(client, h, society):
    r = client.get(f"{P}/societies/{society.id}/services", headers=h)
    assert r.status_code == 200, r.text
    return {s["key"]: s["enabled"] for s in r.json()["services"]}


def test_every_service_is_on_until_switched_off(client, db, two):
    _, h = make_superadmin(db)
    on = _states(client, h, two["a"])
    assert len(on) >= 10 and all(on.values())
    assert {"parking", "visitors", "accounts", "complaints"} <= set(on)
    # Core things aren't listed, so they can't be switched
    assert not {"billing", "residents", "flats", "users"} & set(on)


def test_an_off_service_is_refused_for_that_society_only(client, db, two):
    _, h = make_superadmin(db)
    a, b = two["admin_a"]["headers"], two["admin_b"]["headers"]
    sa, sb = two["a"], two["b"]
    assert client.get(f"{API}/parking/zones/{sa.id}", headers=a).status_code == 200
    assert _switch(client, h, sa, "parking", False).json()["services"]
    assert _states(client, h, sa)["parking"] is False

    r = client.get(f"{API}/parking/zones/{sa.id}", headers=a)
    assert r.status_code == 403 and "Parking is not enabled for your society" in r.json()["detail"]
    # Another society keeps it; the core and the other services of this one keep working
    assert client.get(f"{API}/parking/zones/{sb.id}", headers=b).status_code == 200
    assert client.get(f"{API}/flats/", headers=a).status_code == 200
    assert client.get(f"{API}/complaints/society/{sa.id}", headers=a).status_code == 200
    assert client.get(f"{API}/billing/charges/{sa.id}", headers=a).status_code == 200      # billing is core

    # Switching it back on restores it
    _switch(client, h, sa, "parking", True)
    assert client.get(f"{API}/parking/zones/{sa.id}", headers=a).status_code == 200
    assert _states(client, h, sa)["parking"] is True


def test_the_menu_and_me_follow_the_switches(client, db, two):
    _, h = make_superadmin(db)
    a = two["admin_a"]["headers"]
    forms = client.get(f"{API}/roles/forms/mine", headers=a).json()["form_codes"]
    me = client.get(f"{API}/auth/me", headers=a).json()
    assert "parking_management" in forms and "parking" in me["enabled_services"]

    _switch(client, h, two["a"], "parking", False)
    _switch(client, h, two["a"], "governance", False)
    forms = client.get(f"{API}/roles/forms/mine", headers=a).json()["form_codes"]
    me = client.get(f"{API}/auth/me", headers=a).json()
    assert "parking_management" not in forms and "meetings" not in forms and "polls" not in forms
    assert "complaints" in forms and "residents" in forms                       # the rest stays
    assert "parking" not in me["enabled_services"] and "governance" not in me["enabled_services"]
    assert "complaints" in me["enabled_services"]
    # Another society's menu is untouched
    other = client.get(f"{API}/roles/forms/mine", headers=two["admin_b"]["headers"]).json()["form_codes"]
    assert "parking_management" in other


def test_the_platform_admin_is_never_limited_by_the_switches(client, db, two):
    admin, h = make_superadmin(db)
    _switch(client, h, two["a"], "parking", False)
    # The service check ignores a platform admin (who belongs to no society)...
    assert service_block_reason(db, admin, f"{API}/parking/zones/{two['a'].id}") is None
    # ...and /auth/me reports no limit for them
    assert client.get(f"{API}/auth/me", headers=h).json()["enabled_services"] is None
    # A society user is told why
    assert "Parking is not enabled" in service_block_reason(db, two["admin_a"]["user"], f"{API}/parking/zones/x")


def test_only_the_platform_admin_can_switch_services(client, db, two):
    a = two["admin_a"]["headers"]
    assert _switch(client, a, two["a"], "parking", False).status_code == 403
    assert client.get(f"{P}/societies/{two['a'].id}/services", headers=a).status_code == 403
    _, h = make_superadmin(db)
    assert _switch(client, h, two["a"], "no_such_service", False).status_code == 404
    assert client.put(f"{P}/societies/00000000-0000-0000-0000-000000000000/services/parking",
                      json={"enabled": False}, headers=h).status_code == 404


def test_switching_is_recorded_and_repeating_it_is_harmless(client, db, two):
    _, h = make_superadmin(db)
    _switch(client, h, two["a"], "shops", False)
    _switch(client, h, two["a"], "shops", False)          # already off: nothing new to record
    _switch(client, h, two["a"], "visitors", True)        # already on: nothing to record
    detail = client.get(f"{P}/societies/{two['a'].id}", headers=h).json()
    switched = [e for e in detail["history"] if e["event"] == "service_switched"]
    assert len(switched) == 1
    _switch(client, h, two["a"], "shops", True)
    detail = client.get(f"{P}/societies/{two['a'].id}", headers=h).json()
    assert len([e for e in detail["history"] if e["event"] == "service_switched"]) == 2


def test_a_suspended_society_still_says_suspended_not_service_off(client, db, two):
    _, h = make_superadmin(db)
    _switch(client, h, two["a"], "parking", False)
    client.post(f"{P}/societies/{two['a'].id}/suspend", json={"reason": "Unpaid"}, headers=h)
    r = client.get(f"{API}/parking/zones/{two['a'].id}", headers=two["admin_a"]["headers"])
    assert r.status_code == 403 and "suspended" in r.json()["detail"]


def test_the_dashboard_leaves_out_what_is_switched_off(client, db, two):
    _, h = make_superadmin(db)
    a = two["admin_a"]["headers"]
    url = f"{API}/dashboard/society/{two['a'].id}"
    full = client.get(url, headers=a).json()
    assert full["today"] is not None            # visitors are on
    _switch(client, h, two["a"], "accounts", False)
    _switch(client, h, two["a"], "visitors", False)
    cut = client.get(url, headers=a).json()
    assert cut["money"] is None and cut["today"] is None
    assert cut["occupancy"] is not None and cut["occupancy"]["flats"] == full["occupancy"]["flats"]    # the core stays


def test_every_attention_item_and_form_code_names_a_real_service():
    from app.core.rbac_seed import FORM_DEFINITIONS
    from app.core.services_catalog import BY_KEY, SERVICES
    from app.modules.dashboard.services.dashboard_service import ATTENTION_SERVICE
    assert set(ATTENTION_SERVICE.values()) <= set(BY_KEY)
    codes = {f[0] for f in FORM_DEFINITIONS}
    for service in SERVICES:
        assert set(service.form_codes) <= codes, service.key
