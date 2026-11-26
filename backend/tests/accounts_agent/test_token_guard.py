"""Spending AI tokens only when they add something: the question is cleaned and mapped locally, the app's own data and
earlier answers come first, the monthly budget is respected, and what is sent is small. Claude is never called: its
functions are replaced by stubs that record what they were given."""
from datetime import date

import pytest

from app.modules.accounts_agent.assist import bylaws, claude, entries, prompt_opt, token_guard
from app.modules.accounts_agent.models.agent import AgentAiAnswer, AgentAiUsage
from app.modules.accounts_agent.services.engine import get_settings
from tests.accounts_agent.legal_helpers import LRig
from tests.accounts_agent.test_assist import API, _model

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def rig(db):
    return LRig(db, "tok")


def _ai_on(monkeypatch, db, rig, budget=None):
    monkeypatch.setattr(claude, "configured", lambda: True)
    s = get_settings(db, rig.sid)
    s.llm_provider = "anthropic"
    if budget is not None:
        s.ai_monthly_token_budget = budget
    db.commit()
    return s


def _stub_answer(monkeypatch, calls, tokens=(900, 150)):
    def fake(question, clauses, facts):
        calls.append({"question": question, "clauses": clauses, "facts": facts})
        claude._last.usage = {"input_tokens": tokens[0], "output_tokens": tokens[1]}
        return claude.BylawAnswer(answer="Fourteen clear days [C1].", cited=["C1"], answered_by_sources=True,
                                  needs_professional_review=False)
    monkeypatch.setattr(claude, "answer_bylaw_question", fake)


def _usage(db, rig, feature):
    return db.query(AgentAiUsage).filter(AgentAiUsage.society_id == rig.sid, AgentAiUsage.feature == feature).one()


# ── The question, cleaned locally ──────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,lang,words,gone", [
    ("Namaste sir, kripya batayein ki AGM ke liye kitne din ka notice chahiye??", "hi", ["days"], ["namaste", "sir", "kripya"]),
    ("सभेसाठी किती दिवसांची नोटीस आवश्यक आहे?", "mr", ["meeting", "days", "notice"], []),
    ("थकबाकीवर व्याज किती लावता येते?", "mr", ["arrears", "interest"], []),
    ("किरायेदार के लिए पार्किंग का नियम क्या है? धन्यवाद", "hi", ["tenant", "parking"], ["धन्यवाद"]),
    ("Hello, can you please tell me what is the quorum for a general meeting?? Thanks", "en", [], ["hello", "please", "thanks"]),
])
def test_questions_are_cleaned_and_mapped_without_any_call(text, lang, words, gone):
    q = prompt_opt.normalize(text)
    assert q.language == lang
    assert all(w in q.keywords for w in words)
    assert all(g not in q.text.lower() for g in gone) and "??" not in q.text
    assert q.key() == prompt_opt.normalize(text.upper() if lang == "en" else text).key()   # case does not matter


def test_a_long_clause_is_cut_to_its_relevant_sentences():
    filler = "Unrelated provision about something else entirely. " * 60
    text = "Notice. " + filler + "Fourteen clear days notice of every general meeting shall be given. " + filler
    cut = prompt_opt.relevant_excerpt(text, ["notice", "days"], 400)
    assert len(cut) <= 400 + 10 and "Fourteen clear days" in cut


def test_a_marathi_question_finds_the_english_clause(rig, db):
    _model(rig)
    db.commit()
    q = prompt_opt.normalize("सभेसाठी किती दिवसांची नोटीस आवश्यक आहे?")
    assert bylaws.search(db, rig.sid, q.search_text)[0]["clause_ref"] == "12"


# ── Bye-law answers: reuse, budget, the app's own data, and a small request ────────────────────────────────────────

def test_the_same_question_twice_is_answered_once(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig)
    calls = []
    _stub_answer(monkeypatch, calls)
    a = bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"], s)
    b = bylaws.ask(db, rig.sid, "please, how many days NOTICE for a general meeting", rig.admin["user"], s)
    assert len(calls) == 1
    assert a["answered_from"] == "ai" and b["answered_from"] == "saved_answer" and b["ai_generated"] is True
    assert b["answer"] == a["answer"] and "no AI tokens" in b["token_note"]
    u = _usage(db, rig, "bylaw_answer")
    assert (u.ai_calls, u.reused_answers, u.input_tokens, u.output_tokens) == (1, 1, 900, 150)


def test_what_is_sent_is_small_and_carries_no_society_figures(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig)
    calls = []
    _stub_answer(monkeypatch, calls)
    bylaws.ask(db, rig.sid, "Namaste sir, kripya batayein: notice for general meeting, quorum, interest on arrears rule?",
               rig.admin["user"], s)
    sent = calls[0]
    assert len(sent["clauses"]) <= bylaws.AI_K and sent["facts"] is None
    assert all(len(c["text"]) <= bylaws.AI_CLAUSE_CHARS for c in sent["clauses"])
    assert "Namaste" not in sent["question"] and "kripya" not in sent["question"]


def test_over_budget_lists_the_clauses_and_says_why(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig, budget=0)
    calls = []
    _stub_answer(monkeypatch, calls)
    out = bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"], s)
    assert calls == [] and out["ai_generated"] is False and out["sources"]
    assert "budget is used up" in out["token_note"] and _usage(db, rig, "bylaw_answer").over_budget == 1


def test_the_budget_counts_tokens_already_spent_this_month(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig, budget=1500)
    calls = []
    _stub_answer(monkeypatch, calls, tokens=(1200, 200))
    bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"], s)
    out = bylaws.ask(db, rig.sid, "What is the quorum at a general meeting?", rig.admin["user"], s)
    assert len(calls) == 1 and out["answered_from"] == "library"
    assert token_guard.spent_this_month(db, rig.sid) == 1400


def test_a_question_about_the_societys_own_figures_is_answered_from_the_books(rig, db, monkeypatch):
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig)
    calls = []
    _stub_answer(monkeypatch, calls)
    monkeypatch.setattr(bylaws, "_facts", lambda db, sid, q: "3 flats have arrears of ₹12,000.")
    out = bylaws.ask(db, rig.sid, "How much arrears are pending?", rig.admin["user"], s)
    assert calls == [] and out["society_facts"] and "no AI tokens" in out["token_note"]
    assert _usage(db, rig, "bylaw_answer").answered_locally == 1
    out = bylaws.ask(db, rig.sid, "What interest is allowed on arrears by the bye-laws?", rig.admin["user"], s)
    assert len(calls) == 1 and out["answered_from"] == "ai"        # a rules question still gets the clauses worded


def test_an_edited_clause_is_worded_afresh(rig, db, monkeypatch):
    from app.modules.accounts_agent.legal.models import LegalClause
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig)
    calls = []
    _stub_answer(monkeypatch, calls)
    bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"], s)
    c = db.query(LegalClause).filter(LegalClause.clause_ref == "12").first()
    c.text = c.text.replace("fourteen", "twenty-one")
    db.commit()
    bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"], s)
    assert len(calls) == 2 and db.query(AgentAiAnswer).filter(AgentAiAnswer.society_id == rig.sid).count() == 2


# ── Entries: the app reads the description first ───────────────────────────────────────────────────────────────────

LEDGERS = [{"id": "L1", "name": "Lift Maintenance"}, {"id": "L2", "name": "Housekeeping & Cleaning"},
           {"id": "L3", "name": "Electricity Charges"}, {"id": "L4", "name": "Security Charges"}]
VENDORS = [{"id": "V1", "name": "CleanPro Services"}, {"id": "V2", "name": "Otis Elevators"}]


@pytest.mark.parametrize("text,want", [
    ("Paid ₹12,000 to CleanPro for November housekeeping, bill CP-NOV-26",
     {"amount": "12000", "vendor_id": "V1", "ledger_id": "L2", "reference": "CP-NOV-26", "voucher_type": "payment"}),
    ("लिफ्ट देखभाल 4500 रोख दिले", {"amount": "4500", "ledger_id": "L1", "money_account": "cash"}),
    ("received 3k cash on 03/11/2026", {"amount": "3000", "voucher_type": "receipt", "voucher_date": "2026-11-03"}),
    ("kal electricity bill 8,450 bhara upi", {"amount": "8450", "ledger_id": "L3", "money_account": "bank",
                                              "voucher_date": "2026-11-25", "voucher_type": "payment"}),
    ("paid 12000 for nov 2026 security", {"amount": "12000", "ledger_id": "L4"}),
])
def test_entries_are_read_by_rules(text, want):
    got = entries.read_locally(text, LEDGERS, VENDORS, date(2026, 11, 26))
    assert {k: got.get(k) for k in want} == want


def test_two_amounts_or_a_tied_ledger_are_not_guessed():
    got = entries.read_locally("paid 500 and 700 for charges", LEDGERS, VENDORS, date(2026, 11, 26))
    assert got.get("amount") is None and got["unclear"] and got["ledger_id"] is None


def test_a_readable_entry_costs_no_tokens(rig, db, monkeypatch):
    s = _ai_on(monkeypatch, db, rig)
    called = []
    monkeypatch.setattr(claude, "parse_entry_request", lambda *a: called.append(a))
    name = rig.chart["lift_maintenance"].name
    out = entries.draft(db, rig.sid, rig.admin["user"], {"text": f"paid {name} 4500 cash"}, s, save=False)
    assert called == [] and out["amount"] == "4500.00" and out["lines"][0]["account"] == name
    assert any("by the app (no AI)" in b for b in out["basis"])
    assert _usage(db, rig, "entry_reading").answered_locally == 1


def test_when_the_ai_is_needed_it_gets_only_the_likely_ledgers(rig, db, monkeypatch):
    s = _ai_on(monkeypatch, db, rig)
    seen = {}

    def fake(text, ledgers, vendors, today):
        seen["ledgers"], seen["vendors"] = ledgers, vendors
        claude._last.usage = {"input_tokens": 400, "output_tokens": 80}
        return None
    monkeypatch.setattr(claude, "parse_entry_request", fake)
    with pytest.raises(Exception):
        entries.draft(db, rig.sid, rig.admin["user"], {"text": "settled the yearly one"}, s, save=False)
    assert 0 < len(seen["ledgers"]) <= entries.AI_LIST_SIZE
    u = _usage(db, rig, "entry_reading")
    assert (u.ai_calls, u.failed_calls, u.input_tokens) == (1, 1, 400)


# ── The client reports the tokens each request used ────────────────────────────────────────────────────────────────

def test_the_client_keeps_the_reported_tokens(monkeypatch):
    class U:
        input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens = 300, 90, 0, 50

    class R:
        stop_reason, usage = "end_turn", U()
        parsed_output = claude.BylawAnswer(answer="a", cited=[], answered_by_sources=False,
                                           needs_professional_review=True)
    msgs = type("M", (), {"parse": staticmethod(lambda **k: R())})()
    monkeypatch.setattr(claude, "_client", lambda: type("C", (), {"beta": type("B", (), {"messages": msgs})()})())
    claude.answer_bylaw_question("सभेसाठी नोटीस?", [{"id": "C1", "source": "s", "ref": "12", "text": "t"}])
    assert claude.take_usage() == {"input_tokens": 350, "output_tokens": 90} and claude.take_usage() is None


def test_the_reply_language_follows_the_question():
    p = claude.bylaw_prompt("सभेसाठी किती दिवसांची नोटीस आवश्यक आहे?", [])
    assert "<reply_language>Marathi</reply_language>" in p
    assert "<reply_language>English</reply_language>" in claude.bylaw_prompt("How many days?", [])


# ── API ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_usage_and_budget_api(client, rig, db, monkeypatch):
    _model(rig)
    db.commit()
    s = _ai_on(monkeypatch, db, rig)
    calls = []
    _stub_answer(monkeypatch, calls)
    for _ in range(3):
        bylaws.ask(db, rig.sid, "How many days notice for a general meeting?", rig.admin["user"], s)
    r = client.get(f"{API}/ai-usage", headers=rig.admin["headers"])
    assert r.status_code == 200
    u = r.json()
    assert u["ai_calls"] == 1 and u["reused_answers"] == 2 and u["requests"] == 3 and u["answered_without_ai"] == 2
    assert u["spent_tokens"] == 1050 and u["budget_tokens"] == 300000 and u["kept_answers"] == 1
    assert client.put(f"{API}/settings", json={"ai_monthly_token_budget": -1},
                      headers=rig.admin["headers"]).status_code == 422
    r = client.put(f"{API}/settings", json={"ai_monthly_token_budget": 50000}, headers=rig.admin["headers"])
    assert r.status_code == 200 and r.json()["ai_monthly_token_budget"] == 50000
    assert client.post(f"{API}/ai-usage/forget-answers", headers=rig.admin["headers"]).json() == {"forgotten": 1}
