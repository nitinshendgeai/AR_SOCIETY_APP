"""OCR of scanned bye-laws (PDF and photo, Marathi + English) and reading legacy .doc files.

The fixtures were produced once with LibreOffice (real Devanagari shaping) and are committed: a scan-like PNG, an
image-only PDF of the same page (no text layer), and a Word 97 .doc. Each test checks the real result where the tools
are installed (tesseract with Marathi data, poppler, antiword) and the honest fallback where they are not — never a skip."""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.modules.accounts_agent.legal import documents
from app.modules.accounts_agent.legal.models import LegalClause
from tests.accounts_agent.legal_helpers import LRig

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def rig(db):
    return LRig(db, "ocr")


def _clauses(db, d):
    return {c.clause_ref: c.page_number for c in db.query(LegalClause).filter(LegalClause.document_id == d.id)}


def test_scanned_pdf_is_read_by_ocr(rig, db):
    data = (FIX / "bylaws_scan.pdf").read_bytes()
    d = rig.upload(None, file_name="bylaws_scan.pdf", data=data)
    assert d.data == data
    if not documents.ocr_available():
        assert d.extraction_quality == "OCR_REQUIRED" and any("not installed" in i for i in d.extraction_issues)
        return
    assert d.extraction_method in ("pdftotext+ocr", "ocr") and d.extraction_quality in ("OCR_TEXT", "POOR")
    page = d.pages[0]
    assert page["ocr"] is True and page["ocr_confidence"] is not None
    assert "Service charges shall be shared equally" in d.extracted_text
    assert "उपविधी" in d.extracted_text and d.language in ("mixed", "en")
    assert {"65", "66", "67"} <= set(_clauses(db, d))
    assert any("read by OCR" in i for i in d.extraction_issues)          # always flagged for verification


def test_photo_of_minutes_is_read_by_ocr(rig, db):
    d = rig.upload(None, file_name="minutes.png", data=(FIX / "bylaws_scan.png").read_bytes(),
                   document_type="COMMITTEE_MINUTES", title="MC minutes (photo)")
    if not documents.ocr_available():
        assert d.extraction_quality == "OCR_REQUIRED" and d.extracted_text is None
        return
    assert d.pages[0]["page"] == 1 and "Interest on arrears" in d.extracted_text
    assert _clauses(db, d).get("65") == 1


def test_ocr_text_needs_a_note_to_be_verified(rig, db):
    d = rig.upload(None, file_name="bylaws_scan.pdf", data=(FIX / "bylaws_scan.pdf").read_bytes())
    with pytest.raises(HTTPException) as e:
        documents.verify(db, d, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                         note="ok", approval_date=__import__("datetime").date(2020, 1, 1))
    assert e.value.status_code == 422
    documents.verify(db, d, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="OCR text compared line by line with the Registrar's certified copy",
                     approval_date=__import__("datetime").date(2020, 1, 1))
    assert d.status == "REGISTERED"


def test_legacy_doc_is_read(rig, db):
    import shutil
    d = rig.upload(None, file_name="bylaws.doc", data=(FIX / "bylaws_legacy.doc").read_bytes())
    if not shutil.which("antiword"):
        assert d.extracted_text is None and any("antiword" in i for i in d.extraction_issues)
        return
    assert d.extraction_method == "antiword" and d.extraction_quality == "GOOD"
    assert "Service charges shall be shared equally" in d.extracted_text
    assert {"65", "66", "67"} <= set(_clauses(db, d))
    assert any("no fixed pages" in i for i in d.extraction_issues)


def test_damaged_doc_is_reported_not_guessed(rig):
    d = rig.upload(None, file_name="broken.doc", data=b"this is not a word file at all" * 20)
    assert d.extracted_text is None and d.status == "UNVERIFIED"
    assert d.extraction_issues                                              # says why it could not be read
