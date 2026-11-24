"""Accounts Agent assistant: bye-law answers with clause references, entries drafted for approval, notice drafts.

The bye-law texts below are SYNTHETIC test fixtures (clearly not the real model bye-laws): they only give the clause
splitter and the search something to work on. Claude is never called: its two functions are replaced by stubs, so
the tests check what the app does with whatever the model returns (including bad output)."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent.assist import bylaws, claude, entries, notices
from app.modules.accounts_agent.legal import documents
from app.modules.accounts_agent.models.agent import AgentAuditLog
from app.modules.accounts_agent.services.engine import get_settings
from app.modules.billing.models.billing import ChargeType
from tests.accounts_agent.legal_helpers import D, LRig

API = "/api/v1/accounts-agent"

MODEL_TEXT = """TEST FIXTURE - synthetic model bye-laws
1. Name. The society shall be called as registered.
12. Notice of general meeting. At least fourteen clear days notice of every general meeting shall be given to members.
13. Quorum at general meeting. The quorum shall be two-thirds of members or twenty, whichever is less.
45. Non-occupancy charges. A member who lets a flat on leave and licence shall pay non-occupancy charges.
71. Interest on arrears. Interest shall be charged on dues in arrears at the rate fixed by the general body.
"""
SOCIETY_TEXT = """TEST FIXTURE - synthetic registered bye-laws
45. Non-occupancy charges. Members who let their flats on leave and licence pay non-occupancy charges of ten percent.
"""


@pytest.fixture
def rig(db):
    return LRig(db, "ast")


def _model(rig):
    return documents.upload(rig.db, society_id=None, user=rig.admin["user"], file_name="model.txt",
                            data=MODEL_TEXT.encode(), mime_type=None, document_type="MODEL_BYELAWS",
                            title="Model bye-laws (test fixture)")


def _registered(rig):
    return rig.upload(SOCIETY_TEXT, title="Registered bye-laws (test fixture)")


def _enable_ai(monkeypatch, db, rig):
    monkeypatch.setattr(claude, "configured", lambda: True)
    s = get_settings(db, rig.sid)
    s.llm_provider = "anthropic"
    db.commit()


# ── Bye-law questions ───────────────────────────────────────────────────────────────────────────────────────────────

def test_search_finds_the_clause_and_prefers_the_registered_bye_laws(rig, db):
    _model(rig), _registered(rig)
    db.commit()
    hits = bylaws.search(db, rig.sid, "Can we charge non-occupancy for a rented flat?")
    assert hits and hits[0]["clause_ref"] == "45" and hits[0]["society_specific"] is True
    assert any(h["source"] == "Model bye-laws" and h["clause_ref"] == "45" for h in hits)
    assert bylaws.search(db, rig.sid, "How many days notice for the AGM?")[0]["clause_ref"] == "12"


def test_answer_without_ai_lists_the_clauses_and_flags_model_and_unverified(rig, db):
    _model(rig)
    db.commit()
    out = bylaws.ask(db, rig.sid, "What is the quorum for a general meeting?", rig.admin["user"], get_settings(db, rig.sid))
    assert out["ai_generated"] is False and out["sources"][0]["clause_ref"] == "13"
    assert any("model bye-laws" in n for n in out["notes"]) and any("not been checked" in n for n in out["notes"])
    assert db.query(AgentAuditLog).filter(AgentAuditLog.action == "bylaw_question").count() == 1


def test_no_library_says_what_to_upload(rig, db):
    out = bylaws.ask(db, rig.sid, "What is the quorum?", rig.admin["user"], get_settings(db, rig.sid))
    assert out["sources"] == [] and "platform administrator uploads the model bye-laws" in out["answer"]


def test_ai_answer_is_used_only_with_the_clauses_it_was_given(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    _enable_ai(monkeypatch, db, rig)
    seen = {}

    def fake(question, clauses, facts):
        seen["ids"] = [c["id"] for c in clauses]
        return claude.BylawAnswer(answer="Fourteen clear days [C1].", cited=["C1"], answered_by_sources=True,
                                  needs_professional_review=False)
    monkeypatch.setattr(claude, "answer_bylaw_question", fake)
    out = bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"],
                     get_settings(db, rig.sid))
    assert out["ai_generated"] is True and out["answer"] == "Fourteen clear days [C1]."
    assert seen["ids"][0] == "C1" and [s["cite"] for s in out["sources"] if s["cited"]] == ["C1"]
    assert "Claude" in out["disclaimer"]


def test_ai_citing_something_it_was_not_given_is_discarded(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    _enable_ai(monkeypatch, db, rig)
    monkeypatch.setattr(claude, "answer_bylaw_question", lambda q, c, f: claude.BylawAnswer(
        answer="Section 75 of the Act says 30 days [C99].", cited=["C99"], answered_by_sources=True,
        needs_professional_review=False))
    out = bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"],
                     get_settings(db, rig.sid))
    assert out["ai_generated"] is False and "Section 75" not in out["answer"]


def test_ai_failure_falls_back_to_the_clause_list(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    _enable_ai(monkeypatch, db, rig)
    monkeypatch.setattr(claude, "answer_bylaw_question", lambda q, c, f: None)
    out = bylaws.ask(db, rig.sid, "quorum general meeting", rig.admin["user"], get_settings(db, rig.sid))
    assert out["ai_generated"] is False and out["sources"]


def test_ai_is_off_without_an_api_key(rig, db, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = get_settings(db, rig.sid)
    s.llm_provider = "anthropic"
    assert claude.configured() is False and claude.enabled(s) is False


def test_api_any_member_may_ask_but_only_managers_see_society_figures(client, rig, db):
    from tests.conftest import make_user
    _model(rig)
    db.commit()
    res = make_user(db, "res@ast.com", role="Resident")
    res["user"].society_id = rig.sid
    db.commit()
    q = {"question": "Are there overdue member payments and what interest applies to arrears?"}
    r = client.post(f"{API}/bylaws/ask", json=q, headers=res["headers"])
    assert r.status_code == 200 and r.json()["society_facts"] is None and r.json()["sources"]
    m = client.post(f"{API}/bylaws/ask", json=q, headers=rig.admin["headers"]).json()
    assert m["society_facts"]
    other = LRig(db, "ast2")
    assert client.post(f"{API}/bylaws/ask", json=q, headers=other.admin["headers"],
                       params={"society_id": str(rig.sid)}).status_code == 403


# ── Entries drafted for approval ────────────────────────────────────────────────────────────────────────────────────

def test_preview_saves_nothing_and_save_is_always_pending(client, rig, db):
    from app.modules.billing.models.billing import MaintenanceSettings
    db.add(MaintenanceSettings(society_id=rig.sid, auto_approve_admin_expenses=True))
    db.commit()
    body = {"amount": "12000", "ledger_id": str(rig.chart["housekeeping"].id), "narration": "Housekeeping Nov",
            "reference": "CP-NOV"}
    before = db.query(Voucher).filter(Voucher.society_id == rig.sid).count()
    p = client.post(f"{API}/entries/draft", json=body, headers=rig.admin["headers"]).json()
    assert p["saved"] is False and p["lines"][0]["debit"] == "12000.00"
    assert db.query(Voucher).filter(Voucher.society_id == rig.sid).count() == before
    s = client.post(f"{API}/entries/draft", json={**body, "save": True}, headers=rig.admin["headers"])
    assert s.status_code == 200, s.text
    v = db.get(Voucher, __import__("uuid").UUID(s.json()["voucher_id"]))
    # The society lets admins' payments post directly, but an agent draft stays pending anyway.
    assert v.approval_status == "pending" and "Accounts Agent" in v.approval_note
    assert db.query(AgentAuditLog).filter(AgentAuditLog.action == "entry_drafted").count() == 1
    # The drafter cannot approve it while another committee member exists; the chairman can.
    from app.modules.accounts.services.accounts_service import AccountsService
    with pytest.raises(Exception):
        AccountsService(db).approve_manual_voucher(v.id, rig.admin["user"])
    db.rollback()
    AccountsService(db).approve_manual_voucher(v.id, rig.chair["user"])
    assert db.get(Voucher, v.id).approval_status == "approved"


def test_vendor_usual_ledger_is_used(rig, db):
    rig.seed_history()
    out = entries.draft(db, rig.sid, rig.admin["user"], {"amount": "6100", "vendor_id": rig.clean.id},
                        get_settings(db, rig.sid), save=False)
    assert out["lines"][0]["account"] == "Housekeeping & Cleaning"
    assert any("this vendor's payments" in b for b in out["basis"])


def test_unknown_ledger_is_asked_for_not_guessed(rig, db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        entries.draft(db, rig.sid, rig.admin["user"], {"amount": "500", "text": "misc"}, get_settings(db, rig.sid),
                      save=False)
    assert "Choose the ledger" in e.value.detail


def test_ai_reading_is_checked_against_the_societys_own_lists(rig, db, monkeypatch):
    _enable_ai(monkeypatch, db, rig)
    good = str(rig.chart["lift_maintenance"].id)
    monkeypatch.setattr(claude, "parse_entry_request", lambda text, ledgers, vendors, today: claude.EntryParse(
        voucher_type="payment", amount="4500", ledger_id=good, vendor_id="00000000-0000-0000-0000-000000000000",
        money_account="cash", narration="Lift AMC Nov", unclear=["reference"]))
    out = entries.draft(db, rig.sid, rig.admin["user"], {"text": "paid lift AMC 4500 cash"}, get_settings(db, rig.sid),
                        save=False)
    assert out["amount"] == "4500.00" and out["lines"][0]["account"] == rig.chart["lift_maintenance"].name
    assert out["vendor_id"] is None                      # a vendor id not in this society is dropped
    assert out["lines"][1]["account"] == rig.chart["cash"].name and out["unclear"] == ["reference"]
    monkeypatch.setattr(claude, "parse_entry_request", lambda *a: claude.EntryParse(
        voucher_type="payment", amount="4500", ledger_id=str(rig.chart["bank"].id), narration="x"))
    from fastapi import HTTPException
    with pytest.raises(HTTPException):                   # a bank ledger is not an expense ledger: not accepted
        entries.draft(db, rig.sid, rig.admin["user"], {"text": "x"}, get_settings(db, rig.sid), save=False)


def test_entry_drafting_needs_manager_rights_and_own_society(client, rig, db):
    from tests.conftest import make_user
    res = make_user(db, "res2@ast.com", role="Resident")
    res["user"].society_id = rig.sid
    db.commit()
    body = {"amount": "100", "ledger_id": str(rig.chart["office_expenses"].id)}
    assert client.post(f"{API}/entries/draft", json=body, headers=res["headers"]).status_code == 403
    other = LRig(db, "ast3")
    assert client.post(f"{API}/entries/draft", json=body, headers=other.admin["headers"],
                       params={"society_id": str(rig.sid)}).status_code == 403


# ── Notices and agendas ─────────────────────────────────────────────────────────────────────────────────────────────

def test_agm_notice_cites_the_clause_or_says_none_is_loaded(rig, db):
    out = notices.draft(db, rig.sid, rig.admin["user"], "AGM", {"venue": "Clubhouse"}, save=False)
    assert "no bye-law clause on this is in the Legal Library" in out["content"]
    assert "audited accounts" in out["content"] and "Clubhouse" in out["content"]
    _model(rig)
    db.commit()
    out = notices.draft(db, rig.sid, rig.admin["user"], "AGM", {}, save=False)
    assert "Notice period: see Model bye-laws clause 12" in out["content"]
    assert "Quorum: see Model bye-laws clause 13" in out["content"]
    assert "fourteen" not in out["content"].lower().split("agenda")[0]   # no figure invented in the header


def test_committee_agenda_comes_from_the_books(rig, db):
    v = rig.payment(1, "office_expenses", 900, approved=False)
    v.approval_status = "pending"
    db.commit()
    out = notices.draft(db, rig.sid, rig.admin["user"], "COMMITTEE", {}, save=False)
    assert "1 pending voucher(s) totalling ₹900.00" in out["content"]


def test_dues_reminders_per_defaulter_and_saved_as_drafts_only(client, rig, db):
    from app.modules.notice.models.notice import Notice
    fl = rig.flat_rows[0]
    cy = rig.cycle(rig.today - timedelta(days=200), rig.today - timedelta(days=170), name="Old")
    rig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 3000, 3000)])
    r = client.post(f"{API}/notices/draft", json={"kind": "DUES", "save": True}, headers=rig.admin["headers"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["drafts"]) == 1 and "₹3,000.00" in d["drafts"][0]["content"]
    saved = db.query(Notice).filter(Notice.society_id == rig.sid).all()
    assert len(saved) == 1 and saved[0].status.value == "draft" and saved[0].target_flat_ids == [str(fl.id)]
    assert client.post(f"{API}/notices/draft", json={"kind": "AGM"}, headers=rig.manager["headers"]).status_code == 403


def test_sgm_needs_a_subject(client, rig):
    assert client.post(f"{API}/notices/draft", json={"kind": "SGM"}, headers=rig.admin["headers"]).status_code == 422
    r = client.post(f"{API}/notices/draft", json={"kind": "SGM", "subject": "Terrace waterproofing",
                                                  "resolutions": ["Approve ₹1,50,000 from the repair fund"]},
                    headers=rig.admin["headers"])
    assert r.status_code == 200 and "Resolution 1: Approve ₹1,50,000 from the repair fund" in r.json()["content"]


def test_settings_switch_for_claude(client, rig):
    assert client.put(f"{API}/settings", json={"llm_provider": "openai"}, headers=rig.admin["headers"]).status_code == 422
    r = client.put(f"{API}/settings", json={"llm_provider": "anthropic"}, headers=rig.admin["headers"])
    assert r.status_code == 200 and r.json()["llm_provider"] == "anthropic"
    s = client.get(f"{API}/settings", headers=rig.admin["headers"]).json()
    assert "ai_configured" in s and "ai_enabled" in s


# ── The Claude client itself (no network: the SDK client is replaced) ───────────────────────────────────────────────

class _Resp:
    def __init__(self, stop="end_turn", parsed=None):
        self.stop_reason, self.parsed_output = stop, parsed


class _Messages:
    def __init__(self, fn):
        self.parse = fn


class _Client:
    def __init__(self, beta_fn, plain_fn=None):
        self.beta = type("B", (), {"messages": _Messages(beta_fn)})()
        self.messages = _Messages(plain_fn or (lambda **k: _Resp()))


def test_claude_call_shape_refusal_and_errors(monkeypatch):
    import anthropic
    import httpx2
    calls = []

    def ok(**kw):
        calls.append(kw)
        return _Resp(parsed=claude.BylawAnswer(answer="a", cited=["C1"], answered_by_sources=True,
                                               needs_professional_review=False))
    monkeypatch.setattr(claude, "_client", lambda: _Client(ok))
    out = claude.answer_bylaw_question("q?", [{"id": "C1", "source": "Model bye-laws", "ref": "12", "text": "t"}])
    assert out.answer == "a"
    kw = calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default" and kw["output_format"] is claude.BylawAnswer
    assert "<clause id=\"C1\"" in kw["messages"][0]["content"] and "q?" in kw["messages"][0]["content"]

    monkeypatch.setattr(claude, "_client", lambda: _Client(lambda **k: _Resp(stop="refusal")))
    assert claude.answer_bylaw_question("q", []) is None

    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def down(**k):
        raise anthropic.APIConnectionError(request=req)
    monkeypatch.setattr(claude, "_client", lambda: _Client(down))
    assert claude.answer_bylaw_question("q", []) is None

    def bad_fallback(**k):
        raise anthropic.BadRequestError("fallbacks: not supported", response=httpx2.Response(400, request=req), body=None)
    plain = []
    monkeypatch.setattr(claude, "_client", lambda: _Client(
        bad_fallback, lambda **k: plain.append(k) or _Resp(parsed=claude.BylawAnswer(
            answer="b", cited=[], answered_by_sources=False, needs_professional_review=True))))
    assert claude.answer_bylaw_question("q", []).answer == "b" and "fallbacks" not in plain[0]


def test_committee_notice_never_cites_the_general_meeting_clause(rig, db):
    _model(rig)
    db.commit()
    out = notices.draft(db, rig.sid, rig.admin["user"], "COMMITTEE", {}, save=False)
    assert "clause 12" not in out["content"] and "Notice period: no bye-law clause on this" in out["content"]


def test_society_figures_stay_out_of_the_bye_law_answer_text(rig, db):
    _model(rig)
    db.commit()
    out = bylaws.ask(db, rig.sid, "Are there overdue member payments and what interest applies to arrears?",
                     rig.admin["user"], get_settings(db, rig.sid))
    assert out["society_facts"] and out["society_facts"] not in out["answer"]
