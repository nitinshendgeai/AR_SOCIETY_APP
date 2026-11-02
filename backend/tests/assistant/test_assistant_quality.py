"""Answer quality: does the right manual section come back for the way people actually ask?

QUESTIONS is the set the search was tuned on; HOLDOUT was written afterwards, in different words, to catch a search that
only learned the first set. Each line is (question, the asker's role tags, words one acceptable section/title may contain).
"""
import pytest

from app.modules.assistant import knowledge

QUESTIONS = [
 ("how do I pay my maintenance bill online", ("resident",), ["pay a bill"]),
 ("where can I see my bills", ("resident",), ["see your bills"]),
 ("how to add my car", ("resident",), ["register your vehicle"]),
 ("I want to complain about water leakage", ("resident",), ["raise a complaint"]),
 ("book club house for a function", ("resident",), ["book an amenity"]),
 ("how to allow a guest to come in", ("resident",), ["approve or reject a visitor"]),
 ("how to register my maid", ("resident",), ["maid, cook, driver"]),
 ("change my phone number", ("resident",), ["update your details"]),
 ("get NOC for selling my flat", ("resident",), ["noc or a certificate","certificates and noc"]),
 ("where do I read notices", ("resident",), ["read the notices"]),
 ("my courier parcel at the gate", ("resident",), ["parcels at the gate"]),
 ("how to vote in a poll", ("resident",), ["meetings, polls"]),
 ("a visitor came to the gate what do I do", ("guard",), ["log a visitor"]),
 ("how do I check if a vehicle is allowed", ("guard",), ["check a vehicle"]),
 ("courier delivery at gate", ("guard",), ["log a parcel"]),
 ("maid entry at the gate", ("guard",), ["domestic help at the gate"]),
 ("mark my attendance", ("guard",), ["your attendance"]),
 ("I forgot to punch out", ("staff",), ["forgot to punch"]),
 ("what are my duties today", ("staff",), ["my duties"]),
 ("handover to the next shift", ("staff",), ["handover"]),
 ("how do I approve staff punches", ("manager",), ["approve punches"]),
 ("assign duties to staff", ("manager",), ["give duties"]),
 ("print the duty sheet", ("manager",), ["print the duty sheets"]),
 ("manager daily checklist", ("manager",), ["daily checklist"]),
 ("add a new wing and flats", ("committee",), ["wings, floors and flats"]),
 ("import residents from excel", ("committee",), ["import residents"]),
 ("create a user and give a role", ("committee",), ["users and roles"]),
 ("send a notice to all members", ("committee",), ["notices and emergency"]),
 ("set up maintenance charges", ("committee",), ["charge heads and rules","maintenance elements"]),
 ("generate bills for the month", ("manager",), ["make and issue a bill","monthly routine"]),
 ("record a payment received from a member", ("manager",), ["record payments"]),
 ("waive interest on a flat", ("manager",), ["waive interest"]),
 ("list of defaulters", ("manager",), ["defaulters"]),
 ("add an expense", ("manager",), ["add an expense"]),
 ("close the financial year", ("committee",), ["closing the year"]),
 ("add a vendor", ("manager",), ["vendors","vendor master"]),
 ("work order for lift repair", ("manager",), ["one-time work"]),
 ("annual maintenance contract AMC", ("manager",), ["annual contracts"]),
 ("give a parking slot to a vehicle", ("committee",), ["give a vehicle a slot"]),
 ("add a stock item", ("manager",), ["add an item"]),
 ("register an asset", ("manager",), ["add an asset"]),
 ("I forgot my password", ("resident",), ["sign in","good to know"]),
 ("change language to hindi", ("resident",), ["choose your language"]),
 ("see devices signed in to my account", ("resident",), ["signed-in devices"]),
 ("TDS on vendor bill", ("manager",), ["tds"]),
 ("what is the chart of accounts", ("manager",), ["chart of accounts","standard chart"]),
 ("month end checklist pending vouchers", ("manager",), ["month-end","monthly routine"]),
 ("bank reconciliation", ("manager",), ["bank"]),
 ("charge a fine to one flat", ("manager",), ["fines and extra charges"]),
 ("advance maintenance paid ahead", ("manager",), ["advance maintenance"]),
]


HOLDOUT = [
 ("how can I see my last receipt", ("resident",), ["see your bills","pay a bill","record payments"]),
 ("we have a water tank cleaning, how do I tell everyone", ("committee",), ["notices and emergency"]),
 ("how do I add a new committee member login", ("committee",), ["users and roles"]),
 ("guard forgot to punch in", ("manager",), ["approve punches","forgot to punch"]),
 ("how do I pay the electricity vendor", ("manager",), ["vendor","pay"]),
 ("how are flat charges calculated per sqft", ("manager",), ["charge heads and rules","basis","element"]),
 ("what is a sinking fund", ("manager",), ["sinking","charge heads","element"]),
 ("how to cancel a voucher", ("manager",), ["voucher"]),
 ("entry of bank interest received", ("manager",), ["bank","voucher","entry"]),
 ("how to hire a plumber for one day", ("manager",), ["one-time work","work order"]),
 ("tenant moved out what to do", ("committee",), ["residents and tenants","tenants"]),
 ("how do I upload minutes of meeting", ("committee",), ["meetings and minutes"]),
 ("how to export report as pdf", ("manager",), ["reports"]),
 ("my guest vehicle parking", ("resident",), ["vehicle","parking"]),
]


def _ranks(items):
    index = knowledge.get_index()
    top1 = top3 = 0
    misses = []
    for q, roles, expected in items:
        hits = index.search(q, roles)
        ok = lambda c: any(e in (c.title + " " + c.section).lower() for e in expected)  # noqa: E731
        first = bool(hits) and ok(hits[0][0])
        top1 += first
        top3 += any(ok(c) for c, _ in hits[:3])
        if not first:
            misses.append((q, [c.section[-40:] for c, _ in hits[:3]]))
    return top1, top3, misses


def test_the_right_section_is_found_for_everyday_questions():
    top1, top3, misses = _ranks(QUESTIONS)
    n = len(QUESTIONS)
    assert top3 / n >= 0.96, misses
    assert top1 / n >= 0.88, misses


def test_it_holds_up_on_questions_it_was_not_tuned_on():
    top1, top3, misses = _ranks(HOLDOUT)
    assert top3 / len(HOLDOUT) >= 0.75, misses


@pytest.mark.parametrize("q", ["how do I give feedback", "what is the weather", "what is the capital of france"])
def test_questions_the_manuals_do_not_cover_find_nothing(q):
    assert knowledge.get_index().search(q, ("resident",)) == []


def test_developer_only_sections_are_never_offered():
    index = knowledge.get_index()
    assert not any(".py" in c.section or "/api/" in c.section for c in index.chunks)


def test_the_excerpt_follows_the_question_not_just_the_start_of_the_section():
    long_text = "Intro line about the topic:\n" + "\n".join(f"Filler sentence number {i} about nothing." for i in range(40)) + \
        "\nThe interest rate for late payment is set under Rules."
    out = knowledge.lead_text(long_text, 200, "late payment interest rate")
    assert "interest rate for late payment" in out and "Filler sentence number 0" not in out   # starts at the matching sentence


def test_callouts_do_not_run_words_together():
    assert not any("NoteYou" in c.text or "TipThe" in c.text for c in knowledge.get_index().chunks)


def test_lines_the_manual_wrapped_are_joined_into_one_paragraph():
    text = "The name must be unique. The vendor gets a\ncode (VND-0001).\n\n- first bullet that wraps\n  onto a second line\n- second bullet"
    out = knowledge.lead_text(text, 500)
    assert "gets a code (VND-0001)." in out
    assert "• first bullet that wraps onto a second line" in out and "• second bullet" in out
    assert out.count("\n") == 2
