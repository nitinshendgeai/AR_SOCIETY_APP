"""Importing a bank's Account Statement PDF into the bank reconciliation: who may, which lines are kept, duplicates,
the bank-ledger account-number check, and that a statement that does not add up stores nothing."""
import io
from decimal import Decimal

from sqlalchemy import func

from app.modules.billing.models.billing import BankStatementEntry
from tests.accounts.test_reports import API as ACC, _ledgers
from tests.billing.bank_pdf import build_statement_pdf, row, sample_rows
from tests.conftest import make_society, make_user

IMPORT = "/api/v1/billing/bank-reconciliation/society/{sid}/import"


def _rig(db, tag="pdf1"):
    society = make_society(db, f"Statement Society {tag}")
    manager = make_user(db, f"manager@{tag}.com", role="Manager")
    manager["user"].society_id = society.id
    resident = make_user(db, f"resident@{tag}.com", role="Resident")
    resident["user"].society_id = society.id
    db.commit()
    return society, manager, resident


def _post(client, sid, headers, pdf: bytes, name="statement.pdf", **params):
    return client.post(IMPORT.format(sid=sid), params=params, headers=headers,
                       files={"statement": (name, io.BytesIO(pdf), "application/pdf")})


def _count(db, sid):
    return db.query(func.count(BankStatementEntry.id)).filter(BankStatementEntry.society_id == sid).scalar()


def _credit_rows():
    return [r for r in sample_rows() if r["credit"]]


def test_a_manager_imports_the_credits_of_a_statement(client, db):
    society, manager, _ = _rig(db)
    r = _post(client, society.id, manager["headers"], build_statement_pdf(sample_rows()))
    assert r.status_code == 201, r.text
    entries = r.json()
    assert len(entries) == len(_credit_rows())
    assert {e["direction"] for e in entries} == {"credit"} and {e["match_status"] for e in entries} == {"unmatched"}
    first = entries[0]
    assert (first["amount"], first["reference"], first["txn_date"]) == ("5000.00", "70000001", "2026-10-01")
    assert _count(db, society.id) == len(entries)


def test_debits_are_kept_when_asked_for(client, db):
    society, manager, _ = _rig(db)
    r = _post(client, society.id, manager["headers"], build_statement_pdf(sample_rows()), include_debits=True)
    assert r.status_code == 201, r.text
    directions = [e["direction"] for e in r.json()]
    assert directions.count("debit") == len([x for x in sample_rows() if x["debit"]]) and "credit" in directions


def test_the_summary_says_what_was_read_and_checked(client, db):
    society, manager, _ = _rig(db)
    rows = sample_rows()
    body = _post(client, society.id, manager["headers"], build_statement_pdf(rows), detail="true").json()
    s = body["summary"]
    assert len(body["entries"]) == s["imported"] == len(_credit_rows())
    assert s["file_type"] == "pdf" and s["statement_lines"] == len(rows) and s["totals_checked"] is True
    assert s["skipped_debits"] == len([x for x in rows if x["debit"]]) and s["skipped_duplicates"] == 0
    assert (s["period_from"], s["period_to"]) == ("2026-10-01", "2026-10-31")
    assert Decimal(s["closing_balance"]) == Decimal("100000.00") + sum(r["credit"] or 0 for r in rows) - sum(r["debit"] or 0 for r in rows)
    assert Decimal(s["opening_balance"]) == Decimal("100000.00")


def test_importing_the_same_statement_again_adds_nothing(client, db):
    society, manager, _ = _rig(db)
    pdf = build_statement_pdf(sample_rows())
    first = _post(client, society.id, manager["headers"], pdf, include_debits="true")
    again = _post(client, society.id, manager["headers"], pdf, include_debits="true", detail="true")
    assert first.status_code == 201 and again.status_code == 201
    assert again.json()["entries"] == [] and again.json()["summary"]["skipped_duplicates"] == len(first.json())
    assert _count(db, society.id) == len(first.json())


def test_an_overlapping_statement_adds_only_the_new_lines(client, db):
    society, manager, _ = _rig(db)
    older = sample_rows()[:20]
    newer = sample_rows()[10:30]
    base = Decimal("1000000.00")                      # large enough that the balance never goes below zero
    _post(client, society.id, manager["headers"], build_statement_pdf(older, opening=str(base)))
    # the later statement starts from the balance after the line before its first one
    opening = base + sum((r["credit"] or 0) - (r["debit"] or 0) for r in sample_rows()[:10])
    s = _post(client, society.id, manager["headers"], build_statement_pdf(newer, opening=str(opening)), detail="true").json()["summary"]
    both = {r["ref"] for r in sample_rows()[:30] if r["credit"]}
    assert s["skipped_duplicates"] == len([r for r in sample_rows()[10:20] if r["credit"]])
    assert _count(db, society.id) == len(both)


def test_the_statement_must_belong_to_the_chosen_bank_ledger(client, db):
    society, manager, _ = _rig(db, "pdf2")
    admin = make_user(db, "admin@pdf2.com", role="Society Admin")
    admin["user"].society_id = society.id
    db.commit()
    h, sid = admin["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    assert client.patch(f"{ACC}/ledgers/{L['bank']['id']}", json={"bank_account_number": "9999 8888 7777"}, headers=h).status_code == 200
    pdf = build_statement_pdf(sample_rows(), account="000000000123")
    r = _post(client, sid, h, pdf, bank_account_id=L["bank"]["id"])
    assert r.status_code == 422 and "ending 0123" in r.json()["detail"] and "ending 7777" in r.json()["detail"], r.text
    assert "000000000123" not in r.json()["detail"]                       # only the last four digits are ever quoted
    assert _count(db, society.id) == 0
    # the right number (written with spaces and without the leading zeros) is accepted, and the ledger is recorded
    assert client.patch(f"{ACC}/ledgers/{L['bank']['id']}", json={"bank_account_number": "123"}, headers=h).status_code == 200
    ok = _post(client, sid, h, pdf, bank_account_id=L["bank"]["id"], detail="true")
    assert ok.status_code == 201 and ok.json()["summary"]["bank_ledger"] == L["bank"]["name"]
    assert {e["bank_account_id"] for e in ok.json()["entries"]} == {L["bank"]["id"]}


def test_without_a_chosen_ledger_the_one_with_that_account_number_is_used(client, db):
    society, _, _ = _rig(db, "pdf3")
    admin = make_user(db, "admin@pdf3.com", role="Society Admin")
    admin["user"].society_id = society.id
    db.commit()
    h, sid = admin["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    assert client.patch(f"{ACC}/ledgers/{L['bank']['id']}", json={"bank_account_number": "000000000123"}, headers=h).status_code == 200
    r = _post(client, sid, h, build_statement_pdf(sample_rows()))
    assert r.status_code == 201 and {e["bank_account_id"] for e in r.json()} == {L["bank"]["id"]}


def test_a_statement_that_does_not_add_up_stores_nothing(client, db):
    society, manager, _ = _rig(db, "pdf4")
    bad_balance = build_statement_pdf(sample_rows(), balance_override={5: Decimal("1.00")})
    r = _post(client, society.id, manager["headers"], bad_balance)
    assert r.status_code == 422 and "does not follow" in r.json()["detail"] and "Nothing was imported" in r.json()["detail"]
    credits = sum(x["credit"] or 0 for x in sample_rows())
    bad_total = build_statement_pdf(sample_rows(), printed_totals=(Decimal("1.00"), credits))
    assert _post(client, society.id, manager["headers"], bad_total).status_code == 422
    assert _count(db, society.id) == 0


def test_things_that_are_not_a_readable_statement_are_refused_plainly(client, db):
    society, manager, _ = _rig(db, "pdf5")
    h = manager["headers"]
    from fpdf import FPDF
    receipt = FPDF(unit="pt", format="A4")
    receipt.add_page()
    receipt.set_font("Helvetica", size=10)
    receipt.text(40, 60, "Receipt for maintenance, flat A-101, amount paid 5,500.00 on 05-01-2026")
    notstatement = _post(client, society.id, h, bytes(receipt.output()))
    assert notstatement.status_code == 422 and "No transaction table" in notstatement.json()["detail"]
    broken = _post(client, society.id, h, b"%PDF-1.4\nnot really a pdf")
    assert broken.status_code == 422 and "could not be read" in broken.json()["detail"]
    binary = _post(client, society.id, h, b"\xff\xfe\x00\x01 not text", name="x.bin")
    assert binary.status_code == 422
    huge = _post(client, society.id, h, b"%PDF-" + b"0" * 8_100_000)
    assert huge.status_code == 413
    assert _count(db, society.id) == 0


def test_only_a_manager_of_the_same_society_may_import(client, db):
    society, manager, resident = _rig(db, "pdf6")
    other = make_society(db, "Another Society")
    other_manager = make_user(db, "manager@other-pdf.com", role="Manager")
    other_manager["user"].society_id = other.id
    db.commit()
    pdf = build_statement_pdf(sample_rows())
    assert _post(client, society.id, resident["headers"], pdf).status_code == 403
    assert _post(client, society.id, other_manager["headers"], pdf).status_code == 403
    assert client.post(IMPORT.format(sid=society.id), files={"statement": ("s.pdf", io.BytesIO(pdf), "application/pdf")}).status_code in (401, 403)
    assert _count(db, society.id) == 0


def test_the_csv_import_is_unchanged(client, db):
    society, manager, _ = _rig(db, "pdf7")
    csv_text = "Date,Description,Reference,Amount\n2026-01-05,NEFT CR ACME,UTR999,5500.00\n"
    r = client.post(IMPORT.format(sid=society.id), headers=manager["headers"],
                    files={"statement": ("s.csv", io.BytesIO(csv_text.encode()), "text/csv")})
    assert r.status_code == 201 and isinstance(r.json(), list) and r.json()[0]["amount"] == "5500.00"
    d = client.post(IMPORT.format(sid=society.id), params={"detail": "true"}, headers=manager["headers"],
                    files={"statement": ("s.csv", io.BytesIO(csv_text.encode()), "text/csv")}).json()
    assert d["summary"]["file_type"] == "csv" and len(d["entries"]) == 1


# ── statements from other banks' layouts, through the same import ────────────

from tests.billing.bank_pdf_layouts import LAYOUTS, build_layout_pdf       # noqa: E402


def _layout_pdf(name, rows=None, **kw):
    return build_layout_pdf(LAYOUTS[name], rows or sample_rows(), opening=kw.pop("opening", "1000000.00"), **kw)


def test_other_banks_layouts_import_through_the_same_screen(client, db):
    for n, name in enumerate(LAYOUTS):
        society, manager, _ = _rig(db, f"lay{n}")
        r = _post(client, society.id, manager["headers"], _layout_pdf(name), include_debits="true", detail="true")
        assert r.status_code == 201, (name, r.text)
        body = r.json()
        assert body["summary"]["statement_lines"] == len(sample_rows()) == body["summary"]["imported"], name
        assert body["summary"]["balances_checked"] is True
        assert {e["direction"] for e in body["entries"]} == {"credit", "debit"}


def test_a_statement_with_no_references_is_deduplicated_by_what_each_line_says(client, db):
    society, manager, _ = _rig(db, "noref")
    h = manager["headers"]
    twin = [row("02-Oct-2026", "TO CASH SELF", "x", debit="15000.00", mode="To Csh") for _ in range(2)]
    rows = [row("01-Oct-2026", "NEFT CR SAMPLE PAYER", "x", credit="5000.00")] + twin
    first = _post(client, society.id, h, _layout_pdf("no_reference", rows), include_debits="true", detail="true").json()
    assert first["summary"]["imported"] == 3                          # two identical lines on one day are both real
    again = _post(client, society.id, h, _layout_pdf("no_reference", rows), include_debits="true", detail="true").json()
    assert again["summary"]["imported"] == 0 and again["summary"]["skipped_duplicates"] == 3
    # a later statement that repeats one of them and has a third identical line adds only the third
    more = rows + [row("02-Oct-2026", "TO CASH SELF", "x", debit="15000.00", mode="To Csh")]
    third = _post(client, society.id, h, _layout_pdf("no_reference", more), include_debits="true", detail="true").json()
    assert third["summary"]["imported"] == 1 and third["summary"]["skipped_duplicates"] == 3
    assert _count(db, society.id) == 4


def test_a_masked_account_number_is_matched_by_the_digits_it_shows(client, db):
    society, _, _ = _rig(db, "mask")
    admin = make_user(db, "admin@mask.com", role="Society Admin")
    admin["user"].society_id = society.id
    db.commit()
    h, sid = admin["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    assert client.patch(f"{ACC}/ledgers/{L['bank']['id']}", json={"bank_account_number": "9999 8888 0123"}, headers=h).status_code == 200
    ok = _post(client, sid, h, _layout_pdf("retail_a", account="XXXXXXXX0123"), detail="true")
    assert ok.status_code == 201 and ok.json()["summary"]["bank_ledger"] == L["bank"]["name"], ok.text
    bad = _post(client, sid, h, _layout_pdf("retail_a", rows=sample_rows()[:6], account="XXXXXXXX0456"), bank_account_id=L["bank"]["id"])
    assert bad.status_code == 422 and "ending 0456" in bad.json()["detail"]
