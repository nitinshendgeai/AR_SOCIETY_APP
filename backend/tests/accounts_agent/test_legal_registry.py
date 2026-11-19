"""Legal rule registry, legal hierarchy, verification gates and document registry."""
from datetime import date, datetime

import pytest
from fastapi import HTTPException

from app.modules.accounts_agent.legal import documents, registry
from app.modules.accounts_agent.legal.models import LegalClause, LegalReview, LegalRule
from tests.accounts_agent.legal_helpers import LRig
from tests.security.world import platform_admin


@pytest.fixture
def rig(db):
    return LRig(db, "reg")


def _rule(db, code, version=None):
    q = db.query(LegalRule).filter(LegalRule.rule_code == code, LegalRule.society_id.is_(None))
    if version:
        q = q.filter(LegalRule.version == version)
    return q.order_by(LegalRule.version.desc()).first()


# ── Rule pack and versioning ─────────────────────────────────────────────────────────────────────────────────────

def test_shipped_pack_is_never_claimed_as_verified(rig, db):
    rows = db.query(LegalRule).filter(LegalRule.society_id.is_(None)).all()
    assert rows and all(r.verification_status in ("PENDING_VERIFICATION", "LEGAL_REVIEW_REQUIRED") for r in rows)
    assert {"106C-11", "106C-12", "106C-13", "106C-14"} <= {(r.rule_number or "")[:7] for r in rows}
    assert registry.ensure_jurisdiction_pack(db) == 0          # idempotent


def test_rule_applicable_on_the_transaction_date_superseded_version(rig, db):
    before = registry.resolve(db, rig.sid, "charges.interest_on_arrears.max_rate_pct", date(2026, 5, 1))
    after = registry.resolve(db, rig.sid, "charges.interest_on_arrears.max_rate_pct", date(2026, 7, 1))
    assert before.rule.version == 1 and before.effective_value == 21 and before.rule.legal_status == "SUPERSEDED"
    assert after.rule.version == 2 and after.effective_value == 12
    assert registry.classify(before) == "ADVISORY_OBSERVATION"          # a model-bye-law figure never confirms
    assert registry.classify(after) == "POTENTIAL_NON_COMPLIANCE"        # unverified law: potential only


def test_new_version_never_overwrites_the_old_one(rig, db):
    pa = platform_admin(db, "pa-ver@agent.test")
    old = _rule(db, "MH-CHG-NONOCC-CAP")
    nv = registry.new_version(db, old, {"effective_from": date(2027, 4, 1),
                                        "calculation_method": {"type": "max_pct", "value": 8}}, pa["user"], "revised")
    db.commit()
    db.refresh(old)
    assert old.calculation_method["value"] == 10 and old.superseded_by_id == nv.id
    assert old.effective_until == date(2027, 3, 31) and old.legal_status == "SUPERSEDED"
    assert nv.version == old.version + 1 and nv.verification_status == "PENDING_VERIFICATION"
    assert registry.resolve(db, rig.sid, "charges.non_occupancy.max_pct", date(2027, 1, 1)).effective_value == 10
    assert registry.resolve(db, rig.sid, "charges.non_occupancy.max_pct", date(2027, 5, 1)).effective_value == 8
    with pytest.raises(HTTPException):
        registry.new_version(db, old, {"effective_from": date(2028, 1, 1)}, pa["user"], "again")


def test_marathi_english_discrepancy_blocks_confirmation(rig, db):
    app = registry.resolve(db, rig.sid, "charges.apportionment", rig.today)
    assert app.blocked and any(r.review_type == "NUMBERING_DISCREPANCY" for r in app.blocked_by)
    assert registry.classify(app) == "POTENTIAL_NON_COMPLIANCE"
    slab = registry.resolve(db, rig.sid, "expenditure.committee_limit", rig.today)
    assert slab.rule.rule_code == "MH-EXP-106C13-LIMIT" and slab.rule.calculation_method["slabs"] is None
    assert any(r.review_type == "LANGUAGE_DISCREPANCY" for r in slab.blocked_by)


def test_confirmed_statutory_failure_needs_primary_source_and_no_blocking_review(rig, db):
    pa = platform_admin(db, "pa-conf@agent.test")
    rule = _rule(db, "MH-CHG-INTEREST-CAP", 2)
    # Not verifiable against nothing, nor against a secondary source as primary, nor while a review blocks it.
    gazette = rig.upload("Rule 106C-12 ... interest 12 per cent", document_type="GAZETTE_NOTIFICATION",
                         title="Gazette Part IV-B 22-06-2026", society=False, user=pa["user"], primary=True)
    third_party = rig.upload("copy", document_type="GAZETTE_NOTIFICATION", title="Research copy", society=False,
                             user=pa["user"], primary=False, file_name="copy.txt")
    documents.verify(db, third_party, pa["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="checked")
    with pytest.raises(HTTPException) as e:
        registry.verify_rule(db, rule, pa["user"], "VERIFIED_PRIMARY_SOURCE", "x", "BINDING", third_party.id, "3")
    assert e.value.status_code == 409                                    # the numbering review blocks it first
    rev = db.query(LegalReview).filter(LegalReview.dedupe_key == "gazette-2026:106C-12:numbering").one()
    rev.status = "RESOLVED"
    db.commit()
    with pytest.raises(HTTPException):
        registry.verify_rule(db, rule, pa["user"], "VERIFIED_PRIMARY_SOURCE", "x", "BINDING", third_party.id, "3")
    with pytest.raises(HTTPException):                                   # gazette itself not verified yet
        registry.verify_rule(db, rule, pa["user"], "VERIFIED_PRIMARY_SOURCE", "x", "BINDING", gazette.id, "3")
    documents.verify(db, gazette, pa["user"], status="REGISTERED", verification_status="VERIFIED_PRIMARY_SOURCE",
                     note="Original Gazette", approval_date=date(2026, 6, 22))
    with pytest.raises(HTTPException):                                   # page reference required
        registry.verify_rule(db, rule, pa["user"], "VERIFIED_PRIMARY_SOURCE", "x", "BINDING", gazette.id, None)
    registry.verify_rule(db, rule, pa["user"], "VERIFIED_PRIMARY_SOURCE", "checked p.3", "BINDING", gazette.id, "3")
    db.commit()
    app = registry.resolve(db, rig.sid, "charges.interest_on_arrears.max_rate_pct", rig.today)
    assert registry.classify(app) == "CONFIRMED_STATUTORY_VALIDATION_FAILURE"
    assert registry.classify(app, deterministic=False) == "POTENTIAL_NON_COMPLIANCE"


def test_society_cannot_verify_or_revise_state_law(rig, db):
    rule = _rule(db, "MH-FUND-SINKING-RATE")
    with pytest.raises(HTTPException) as e:
        registry.verify_rule(db, rule, rig.admin["user"], "VERIFIED_SECONDARY_SOURCE", "ok", None, None, "1")
    assert e.value.status_code == 403


# ── Hierarchy: bye-law override attempt, stricter bye-law ────────────────────────────────────────────────────────

def _society_rule(rig, db, value, code="SOC-INT"):
    doc = rig.upload("Bye-law No. 70. Interest on arrears at 18 per cent per annum.", title="Registered bye-laws 2020")
    documents.verify(db, doc, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="Certified copy from the Registrar", approval_date=date(2020, 5, 1))
    r = LegalRule(scope=str(rig.sid), society_id=rig.sid, rule_code=code, version=1,
                  topic="charges.interest_on_arrears.max_rate_pct", rule_category="charges", title="Bye-law 70 interest",
                  source_level="D", source_document_id=doc.id, legal_status="UNVERIFIED",
                  verification_status="PENDING_VERIFICATION", calculation_method={"type": "max_pct", "value": value})
    db.add(r)
    db.commit()
    return doc, r


def test_unverified_society_rule_does_not_govern(rig, db):
    _, r = _society_rule(rig, db, 10)
    app = registry.resolve(db, rig.sid, "charges.interest_on_arrears.max_rate_pct", rig.today)
    assert r in app.not_operative and app.effective_value == 12


def test_bye_law_cannot_relax_statutory_ceiling(rig, db):
    _, r = _society_rule(rig, db, 18)
    registry.verify_rule(db, r, rig.admin["user"], "VERIFIED_SECONDARY_SOURCE", "certified copy", "BINDING", None, "14")
    db.commit()
    app = registry.resolve(db, rig.sid, "charges.interest_on_arrears.max_rate_pct", rig.today)
    assert app.rule.source_level == "A" and app.effective_value == 12
    assert [c["type"] for c in app.conflicts] == ["BYELAW_OVERRIDE_ATTEMPT"]
    reviews = registry.detect_conflicts(db, rig.sid, rig.today)
    assert any(rv.review_type == "BYELAW_OVERRIDE_ATTEMPT" and rv.society_id == rig.sid for rv in reviews)


def test_stricter_bye_law_is_honoured(rig, db):
    _, r = _society_rule(rig, db, 10)
    registry.verify_rule(db, r, rig.admin["user"], "VERIFIED_SECONDARY_SOURCE", "certified copy", "BINDING", None, "14")
    db.commit()
    app = registry.resolve(db, rig.sid, "charges.interest_on_arrears.max_rate_pct", rig.today)
    assert app.effective_value == 10 and not app.conflicts


# ── Documents ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_upload_keeps_original_hash_and_never_makes_it_operative(rig, db):
    text = "Bye-law No. 65. Charges.\nThe society shall levy charges.\n66. Service charges shall be shared equally."
    d = rig.upload(text, requested_status="REGISTERED")
    assert d.status == "UNVERIFIED" and d.requested_status == "REGISTERED"
    assert d.data == text.encode() and d.sha256 == documents.sha256(text.encode())
    refs = [c.clause_ref for c in db.query(LegalClause).filter(LegalClause.document_id == d.id)]
    assert refs == ["65", "66"]
    dup = rig.upload(text, title="Same again")
    assert dup.duplicate_of_id == d.id and any("Identical" in i for i in dup.extraction_issues)


def test_marathi_document_language_and_clauses(rig, db):
    d = rig.upload("उपविधी क्र. ६५. संस्थेच्या खर्चाची वसुली सदस्यांकडून केली जाईल.\n६६. सेवा शुल्क", title="उपविधी")
    assert d.language == "mr"
    assert [c.clause_ref for c in db.query(LegalClause).filter(LegalClause.document_id == d.id)] == ["65", "66"]


def test_pdf_pages_and_missing_page_detection(rig, db):
    import io
    import shutil
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, "Bye-law No. 157. The committee may incur expenditure up to the limit fixed.")
    c.showPage()
    c.showPage()                                         # an empty (scanned / missing) page
    c.drawString(72, 750, "Bye-law No. 158. Tenders shall be invited above the limit.")
    c.save()
    d = rig.upload(None, file_name="bylaws.pdf", data=buf.getvalue())
    assert d.data == buf.getvalue()                      # the original is kept either way
    if not shutil.which("pdftotext"):
        # No extractor on this server: the PDF is stored, flagged for OCR / manual transcription and never
        # treated as readable text.
        assert d.extraction_quality == "OCR_REQUIRED" and d.extracted_text is None and d.status == "UNVERIFIED"
        assert any("pdftotext" in i for i in d.extraction_issues)
        assert db.query(LegalClause).filter(LegalClause.document_id == d.id).count() == 0
        return
    assert d.page_count == 3 and d.extraction_quality == "POOR"
    assert any("Page(s) 2" in i for i in d.extraction_issues)
    clauses = {c.clause_ref: c.page_number for c in db.query(LegalClause).filter(LegalClause.document_id == d.id)}
    assert clauses == {"157": 1, "158": 3}


def test_draft_bye_law_cannot_be_verified_as_registered(rig, db):
    d = rig.upload("DRAFT bye-laws for discussion. Bye-law No. 1. Name.", requested_status="REGISTERED")
    assert any("draft" in i.lower() for i in d.extraction_issues)
    with pytest.raises(HTTPException) as e:
        documents.verify(db, d, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                         note="looks fine", approval_date=date(2024, 1, 1))
    assert e.value.status_code == 409 and d.status == "UNVERIFIED"
    documents.verify(db, d, rig.admin["user"], status="DRAFT", verification_status="PENDING_VERIFICATION", note="draft")
    assert d.status == "DRAFT"


def test_document_type_must_fit_status(rig, db):
    d = rig.upload("Minutes of the committee meeting", document_type="COMMITTEE_MINUTES", title="MC minutes")
    with pytest.raises(HTTPException):
        documents.verify(db, d, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                         note="x", approval_date=date(2024, 1, 1))
    with pytest.raises(HTTPException):          # verification needed to become operative
        documents.verify(db, d, rig.admin["user"], status="COMMITTEE_APPROVED", verification_status="PENDING_VERIFICATION",
                         note="x")
    documents.verify(db, d, rig.admin["user"], status="COMMITTEE_APPROVED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="signed minutes")
    assert d.status == "COMMITTEE_APPROVED"


def test_new_registered_bye_laws_supersede_the_old(rig, db):
    old = rig.upload("Bye-law No. 1. Old.", title="2014 bye-laws")
    documents.verify(db, old, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="ok", approval_date=date(2014, 1, 1))
    new = rig.upload("Bye-law No. 1. New.", title="2024 bye-laws")
    documents.verify(db, new, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="ok", approval_date=date(2024, 1, 1), effective_from=date(2024, 2, 1))
    db.commit()
    assert old.status == "SUPERSEDED" and old.superseded_by_id == new.id
    assert registry.profile_for(db, rig.sid).registered_bylaw_document_id == new.id
    with pytest.raises(HTTPException):
        documents.verify(db, old, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                         note="again", approval_date=date(2014, 1, 1))


def test_society_cannot_record_state_law_as_its_own(rig, db):
    with pytest.raises(HTTPException):
        rig.upload("Act text", document_type="ACT", title="MCS Act")
