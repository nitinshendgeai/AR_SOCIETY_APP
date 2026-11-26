"""AI is part of the subscription: the platform administrator decides which plans include it and how many tokens,
can override one society, and an expired / suspended / cancelled subscription or an ended trial gets no AI at all.
The society's committee can only spend less. Claude is never called: its function is a stub that counts calls."""
from datetime import date, timedelta

import pytest

from app.models.society import AccountStatus
from app.modules.accounts_agent.assist import bylaws, claude, entitlement, token_guard
from app.modules.accounts_agent.models.agent import AgentAiUsage
from app.modules.accounts_agent.services.engine import get_settings
from tests.accounts_agent.legal_helpers import LRig
from tests.accounts_agent.test_assist import API, _model
from tests.platform_admin.test_platform_admin import make_superadmin

P = "/api/v1/platform-admin"
Q = "How many days notice for a general meeting?"


@pytest.fixture
def rig(db, monkeypatch):
    r = LRig(db, "sub")
    _model(r)
    monkeypatch.setattr(claude, "configured", lambda: True)
    s = get_settings(db, r.sid)
    s.llm_provider = "anthropic"
    db.commit()
    r.calls = []

    def fake(question, clauses, facts):
        r.calls.append(question)
        claude._last.usage = {"input_tokens": 1000, "output_tokens": 200}
        return claude.BylawAnswer(answer="Fourteen clear days [C1].", cited=["C1"], answered_by_sources=True,
                                  needs_professional_review=False)
    monkeypatch.setattr(claude, "answer_bylaw_question", fake)
    return r


def _on(db, rig, status, plan=None, expiry=None, trial_end=None, trial_start=None):
    s = rig.society
    s.account_status, s.subscription_plan, s.subscription_expiry_date = status, plan, expiry
    s.trial_end_date, s.trial_start_date, s.is_trial = trial_end, trial_start, status == AccountStatus.TRIAL
    db.commit()


def _ask(db, rig, q=Q):
    return bylaws.ask(db, rig.sid, q, rig.admin["user"], get_settings(db, rig.sid))


@pytest.mark.parametrize("status,plan,allowed,tokens,period", [
    (AccountStatus.ACTIVE, "growth", True, 300_000, "month"),
    (AccountStatus.ACTIVE, "enterprise", True, 1_000_000, "month"),
    (AccountStatus.ACTIVE, "starter", False, 0, "month"),
    (AccountStatus.TRIAL, None, True, 50_000, "trial"),
    (AccountStatus.EXPIRED, "growth", False, 0, "month"),
    (AccountStatus.SUSPENDED, "growth", False, 0, "month"),
    (AccountStatus.CANCELLED, "enterprise", False, 0, "month"),
])
def test_what_each_subscription_includes(rig, db, status, plan, allowed, tokens, period):
    _on(db, rig, status, plan)
    e = entitlement.entitlement(db, rig.sid, get_settings(db, rig.sid))
    assert (e["allowed"], e["tokens"], e["period"]) == (allowed, tokens, period)
    assert (e["reason"] is None) == allowed


def test_a_run_out_subscription_or_trial_stops_ai_at_once_even_if_not_marked(rig, db):
    yesterday = date.today() - timedelta(days=1)
    _on(db, rig, AccountStatus.ACTIVE, "growth", expiry=yesterday)
    out = _ask(db, rig)
    assert rig.calls == [] and out["ai_generated"] is False and "run out" in out["token_note"]
    _on(db, rig, AccountStatus.TRIAL, trial_end=yesterday)
    out = _ask(db, rig)
    assert rig.calls == [] and "trial has ended" in out["token_note"]
    assert db.query(AgentAiUsage).filter(AgentAiUsage.society_id == rig.sid).one().not_included == 2
    assert out["sources"]                                # the clauses are still listed


def test_a_plan_without_ai_lists_the_clauses_and_says_so(rig, db):
    _on(db, rig, AccountStatus.ACTIVE, "starter")
    out = _ask(db, rig)
    assert rig.calls == [] and "Starter plan does not include AI" in out["token_note"]
    assert out["ai_available"] is False


def test_the_trial_allowance_covers_the_whole_trial(rig, db, monkeypatch):
    _on(db, rig, AccountStatus.TRIAL, trial_start=date.today() - timedelta(days=40),
        trial_end=date.today() + timedelta(days=5))
    monkeypatch.setattr(entitlement, "DEFAULTS", {**entitlement.DEFAULTS, "trial": (True, 2_000)})
    # tokens spent in an earlier month of the trial count too
    earlier = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    db.add(AgentAiUsage(society_id=rig.sid, month=earlier, feature="bylaw_answer", ai_calls=1, input_tokens=900,
                        output_tokens=100, reused_answers=0, answered_locally=0, over_budget=0, not_included=0,
                        failed_calls=0))
    db.commit()
    out = _ask(db, rig)
    assert rig.calls == [] and "trial's AI allowance is used up" in out["token_note"]


def test_the_plan_allowance_caps_the_committee_budget(rig, db, monkeypatch):
    _on(db, rig, AccountStatus.ACTIVE, "growth")
    monkeypatch.setattr(entitlement, "DEFAULTS", {**entitlement.DEFAULTS, "growth": (True, 1_500)})
    _ask(db, rig)
    out = _ask(db, rig, "What is the quorum at a general meeting?")
    assert len(rig.calls) == 1 and "allowance in the Growth plan is used up" in out["token_note"]
    u = token_guard.summary(db, rig.sid, get_settings(db, rig.sid))
    assert u["budget_tokens"] == 1_500 and u["committee_budget"] == 300_000 and u["entitlement"]["plan"] == "growth"


def test_the_committee_can_only_spend_less(rig, db):
    _on(db, rig, AccountStatus.ACTIVE, "growth")
    s = get_settings(db, rig.sid)
    s.ai_monthly_token_budget = 1_000
    db.commit()
    out = _ask(db, rig)
    assert rig.calls == [] and "committee can raise it" in out["token_note"]
    assert token_guard.summary(db, rig.sid, s)["budget_tokens"] == 1_000


# ── The platform administrator ──────────────────────────────────────────────────────────────────────────────────────

def test_platform_admin_sets_what_plans_include(client, db, rig):
    _, h = make_superadmin(db)
    plans = {p["plan_key"]: p for p in client.get(f"{P}/ai-plans", headers=h).json()["plans"]}
    assert plans["starter"]["ai_included"] is False and plans["trial"]["period"] == "trial"
    r = client.put(f"{P}/ai-plans/starter", json={"ai_included": True, "tokens": 80_000}, headers=h)
    assert r.status_code == 200
    _on(db, rig, AccountStatus.ACTIVE, "starter")
    e = entitlement.entitlement(db, rig.sid, get_settings(db, rig.sid))
    assert e["allowed"] and e["tokens"] == 80_000
    assert client.put(f"{P}/ai-plans/gold", json={"ai_included": True, "tokens": 1}, headers=h).status_code == 404
    assert client.put(f"{P}/ai-plans/starter", json={"ai_included": True, "tokens": -1}, headers=h).status_code == 422
    # a society admin cannot change plans
    assert client.put(f"{P}/ai-plans/starter", json={"ai_included": True, "tokens": 9},
                      headers=rig.admin["headers"]).status_code == 403


def test_platform_admin_overrides_one_society(client, db, rig):
    _, h = make_superadmin(db)
    _on(db, rig, AccountStatus.ACTIVE, "starter")
    r = client.put(f"{P}/societies/{rig.sid}/ai", json={"mode": "on", "tokens": 25_000}, headers=h)
    assert r.status_code == 200 and r.json()["entitlement"]["allowed"] and r.json()["budget_tokens"] == 25_000
    _ask(db, rig)
    assert len(rig.calls) == 1
    assert client.put(f"{P}/societies/{rig.sid}/ai", json={"mode": "off"}, headers=h).status_code == 200
    out = _ask(db, rig, "What is the quorum at a general meeting?")
    assert len(rig.calls) == 1 and "switched off for this society by DUX OS" in out["token_note"]
    d = client.get(f"{P}/societies/{rig.sid}/ai", headers=h).json()
    assert d["override"]["mode"] == "off" and d["ai_calls"] == 1 and d["not_included"] == 1
    # the society itself can neither see nor set the override
    r = client.put(f"{API}/settings", json={"ai_plan_override": "on", "ai_override_tokens": 9_000_000},
                   headers=rig.admin["headers"])
    assert r.status_code == 200 and get_settings(db, rig.sid).ai_plan_override == "off"
    assert client.put(f"{P}/societies/{rig.sid}/ai", json={"mode": "on"},
                      headers=rig.admin["headers"]).status_code == 403


def test_society_settings_say_what_the_plan_includes(client, db, rig):
    _on(db, rig, AccountStatus.ACTIVE, "starter")
    s = client.get(f"{API}/settings", headers=rig.admin["headers"]).json()
    assert s["ai_included"] is False and s["ai_enabled"] is False and "Starter plan does not include AI" in s["ai_plan_reason"]
    _on(db, rig, AccountStatus.ACTIVE, "growth")
    s = client.get(f"{API}/settings", headers=rig.admin["headers"]).json()
    assert s["ai_included"] is True and s["ai_enabled"] is True and s["ai_plan_tokens"] == 300_000
