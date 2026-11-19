"""Legal document registry: keep the original, hash it, extract text page by page, find clauses, and — only after an
authorised person verifies it — let it govern compliance.

Extraction is deliberately conservative and offline (no paid API, no network):
- PDF: `pdftotext` (poppler) page by page when it is installed; a page with almost no text is reported as needing OCR.
  No OCR engine is bundled, so a scanned PDF is stored, flagged OCR_REQUIRED and needs human transcription/verification.
- DOCX: the document XML is read with the standard library (no page numbers exist in a DOCX; that is reported).
- DOC (legacy Word): stored but not parsed; flagged for manual extraction.
- TXT: decoded as UTF-8.
Language is detected from the share of Devanagari characters (Marathi text), and draft markers in English or Marathi
("draft", "proposed", "प्रारूप", "मसुदा") are reported so a draft cannot slip in as a registered bye-law.
"""
import hashlib
import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date, datetime
from typing import List, Optional, Tuple
from uuid import UUID
from xml.etree import ElementTree

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts_agent.legal.models import (
    DOCUMENT_STATUSES, DOCUMENT_TYPES, JURISDICTION_MH, OPERATIVE_DOCUMENT_STATUSES, VERIFIED, LegalClause,
    LegalDocument, LegalProfile, LegalReview,
)
from app.modules.accounts_agent.services import audit

MAX_BYTES = 15 * 1024 * 1024
ALLOWED_EXT = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               ".doc": "application/msword", ".txt": "text/plain"}
DRAFT_MARKERS = re.compile(r"\b(draft|proposed|for discussion|not for circulation)\b|प्रारूप|मसुदा|प्रस्तावित", re.I)
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")
MARATHI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
CLAUSE_START = re.compile(
    r"^\s*(?:(?:bye[- ]?law|rule|section|clause|उपविधी|नियम|कलम)\s*(?:no\.?|क्र\.?)?\s*)?"
    r"(\d{1,3}[A-Z]?(?:-\d{1,3})?(?:\s*\([a-z0-9ivx]{1,4}\))*)\s*[\.\):–-]\s+(\S.{2,200})$", re.I)
# Which statuses fit which document types: a set of minutes cannot become a "registered bye-law".
STATUS_FOR_TYPE = {
    "REGISTERED_BYELAWS": ("REGISTERED",), "BYELAW_AMENDMENT": ("APPROVED_AMENDMENT",),
    "AGM_MINUTES": ("GENERAL_BODY_APPROVED",), "SGM_MINUTES": ("GENERAL_BODY_APPROVED",), "BUDGET": ("GENERAL_BODY_APPROVED",),
    "COMMITTEE_MINUTES": ("COMMITTEE_APPROVED",),
    "VENDOR_APPROVAL_POLICY": ("COMMITTEE_APPROVED", "GENERAL_BODY_APPROVED"),
    "ACCOUNTING_POLICY": ("COMMITTEE_APPROVED", "GENERAL_BODY_APPROVED"),
}
JURISDICTION_OPERATIVE = ("REGISTERED",)   # law as published: recorded as REGISTERED once verified


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_language(text: str) -> str:
    dev, lat = len(DEVANAGARI.findall(text or "")), len(LATIN.findall(text or ""))
    if not dev and not lat:
        return "unknown"
    share = dev / (dev + lat)
    return "mr" if share > 0.7 else ("en" if share < 0.1 else "mixed")


def _pdf_pages(data: bytes) -> Tuple[Optional[List[str]], str, List[str]]:
    if not shutil.which("pdftotext"):
        return None, "none", ["PDF text extraction is not installed on this server (poppler pdftotext); the file is "
                              "stored and must be transcribed or verified manually."]
    with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
        fh.write(data)
        fh.flush()
        try:
            res = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", fh.name, "-"], capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return None, "pdftotext", ["Text extraction timed out"]
    if res.returncode != 0:
        return None, "pdftotext", ["The PDF could not be read (damaged or encrypted)"]
    text = res.stdout.decode("utf-8", "replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages, "pdftotext", []


def _docx_text(data: bytes) -> Tuple[Optional[List[str]], str, List[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        return None, "docx-xml", ["The DOCX file could not be opened"]
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ElementTree.fromstring(xml)
    paras = ["".join(t.text or "" for t in p.iter(f"{ns}t")) for p in root.iter(f"{ns}p")]
    return ["\n".join(paras)], "docx-xml", ["A DOCX has no fixed pages: clause page references are not available"]


def extract(file_name: str, data: bytes) -> dict:
    ext = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""
    issues: List[str] = []
    if ext == ".pdf":
        pages, method, issues = _pdf_pages(data)
    elif ext == ".docx":
        pages, method, issues = _docx_text(data)
    elif ext == ".txt":
        pages, method = [data.decode("utf-8", "replace")], "text"
    else:
        pages, method, issues = None, "none", ["Legacy .doc files are stored but not parsed; save as DOCX or PDF, or "
                                               "transcribe the clauses manually"]
    if pages is None:
        return {"pages": None, "text": None, "method": method, "quality": "OCR_REQUIRED" if ext == ".pdf" else "NONE",
                "issues": issues, "language": "unknown", "draft_markers": []}
    page_rows, weak = [], []
    for i, t in enumerate(pages, start=1):
        chars = len(t.strip())
        page_rows.append({"page": i if ext == ".pdf" else None, "text": t, "chars": chars})
        if ext == ".pdf" and chars < 40:
            weak.append(i)
    text = "\n".join(p["text"] for p in page_rows)
    if ext == ".pdf" and weak:
        issues.append(f"Page(s) {', '.join(map(str, weak[:20]))} have little or no text: scanned image or missing page — "
                      "OCR / manual verification needed")
    quality = "GOOD"
    if ext == ".pdf" and page_rows and len(weak) == len(page_rows):
        quality = "OCR_REQUIRED"
    elif weak or "�" in text:
        quality = "POOR"
    if "�" in text:
        issues.append("Some characters could not be decoded (font encoding); verify the Marathi text against the original")
    markers = sorted({m.group(0).lower() for m in DRAFT_MARKERS.finditer(text[:20000])})
    if markers:
        issues.append(f"The text contains draft markers ({', '.join(markers)}): confirm this is the final, registered "
                      "version before verifying it")
    return {"pages": page_rows, "text": text, "method": method, "quality": quality, "issues": issues,
            "language": detect_language(text), "draft_markers": markers}


def extract_clauses(pages: Optional[List[dict]], language: str) -> List[dict]:
    """Numbered clauses with the page they start on. Every extracted clause needs human verification."""
    out: List[dict] = []
    cur = None
    for p in pages or []:
        for line in (p["text"] or "").splitlines():
            m = CLAUSE_START.match(line.translate(MARATHI_DIGITS))
            if m:
                if cur:
                    out.append(cur)
                ref = re.sub(r"\s+", "", m.group(1))
                cur = {"clause_ref": ref[:60], "heading": m.group(2).strip()[:300], "page_number": p["page"],
                       "language": detect_language(line) if language == "mixed" else language, "text": line.strip()}
            elif cur and line.strip():
                if len(cur["text"]) < 8000:
                    cur["text"] += "\n" + line.strip()
    if cur:
        out.append(cur)
    return out[:2000]


def upload(db: Session, *, society_id: Optional[UUID], user, file_name: str, data: bytes, mime_type: Optional[str],
           document_type: str, title: str, requested_status: Optional[str] = None, source_authority: Optional[str] = None,
           source_url: Optional[str] = None, is_primary_source: bool = False, reference_number: Optional[str] = None,
           issue_date: Optional[date] = None, approval_date: Optional[date] = None,
           effective_from: Optional[date] = None, jurisdiction: str = JURISDICTION_MH) -> LegalDocument:
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(422, "Unknown document type")
    level, owner = DOCUMENT_TYPES[document_type]
    if owner == "jurisdiction" and society_id is not None:
        raise HTTPException(422, "This is jurisdiction-wide law; a platform administrator records it once for every "
                                 "society. Upload your society's own copy as a legal opinion or other document.")
    if owner == "society" and society_id is None:
        raise HTTPException(422, "This document belongs to a society; name the society")
    if requested_status and requested_status not in DOCUMENT_STATUSES:
        raise HTTPException(422, "Unknown document status")
    ext = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(422, "Upload a PDF, DOCX, DOC or TXT file")
    if not data:
        raise HTTPException(422, "The file is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "The file is larger than 15 MB")
    if is_primary_source and society_id is not None:
        is_primary_source = False          # only the platform records an original government publication
    digest = sha256(data)
    dup = (db.query(LegalDocument).filter(LegalDocument.sha256 == digest,
                                          (LegalDocument.society_id == society_id) if society_id else LegalDocument.society_id.is_(None))
           .order_by(LegalDocument.created_at).first())
    ex = extract(file_name, data)
    issues = list(ex["issues"])
    if dup:
        issues.append(f"Identical to the document '{dup.title}' already uploaded (same SHA-256)")
    doc = LegalDocument(
        society_id=society_id, jurisdiction=jurisdiction, document_type=document_type, source_level=level, title=title[:300],
        source_authority=source_authority, source_url=source_url, is_primary_source=is_primary_source,
        reference_number=reference_number, file_name=file_name[:255], mime_type=mime_type or ALLOWED_EXT[ext],
        size_bytes=len(data), data=data, sha256=digest, language=ex["language"], extracted_text=ex["text"],
        pages=[{k: v for k, v in p.items()} for p in ex["pages"]] if ex["pages"] else None,
        page_count=len(ex["pages"]) if ex["pages"] else None, extraction_method=ex["method"],
        extraction_quality=ex["quality"], extraction_issues=issues, issue_date=issue_date, approval_date=approval_date,
        effective_from=effective_from, status="UNVERIFIED", requested_status=requested_status,
        verification_status="PENDING_VERIFICATION", duplicate_of_id=dup.id if dup else None, uploaded_by=user.id)
    db.add(doc)
    db.flush()
    for c in extract_clauses(ex["pages"], ex["language"]):
        db.add(LegalClause(document_id=doc.id, society_id=society_id, needs_verification=True, **c))
    if society_id and (ex["draft_markers"] or ex["quality"] in ("OCR_REQUIRED", "POOR")):
        db.add(LegalReview(scope=str(society_id), society_id=society_id, review_type="DOCUMENT_VERIFICATION",
                           dedupe_key=f"document:{doc.id}", blocking=False, status="OPEN",
                           title=f"Check '{doc.title[:200]}' before it is relied on",
                           description="; ".join(issues) or "Extraction needs checking", document_ids=[str(doc.id)]))
    if society_id:
        audit.record(db, society_id, "legal_document_uploaded", "legal_document", doc.id, user.id,
                     {"type": document_type, "sha256": digest[:16], "quality": ex["quality"]})
    db.flush()
    return doc


def verify(db: Session, doc: LegalDocument, user, *, status: str, verification_status: str, note: str,
           issue_date: Optional[date] = None, approval_date: Optional[date] = None,
           effective_from: Optional[date] = None, effective_until: Optional[date] = None,
           override_draft_warning: Optional[str] = None) -> LegalDocument:
    """Make a document operative (or record it as a draft / reject it). Uploading alone never does this."""
    if status not in DOCUMENT_STATUSES or status == "SUPERSEDED":
        raise HTTPException(422, "Unknown status (a document is superseded by verifying its replacement)")
    if verification_status not in ("VERIFIED_PRIMARY_SOURCE", "VERIFIED_SECONDARY_SOURCE", "LEGAL_REVIEW_REQUIRED",
                                   "REJECTED_SOURCE", "PENDING_VERIFICATION"):
        raise HTTPException(422, "Unknown verification status")
    if doc.society_id is None and user.society_id is not None:
        raise HTTPException(403, "Jurisdiction-wide law is verified by a platform administrator")
    if doc.status == "SUPERSEDED":
        raise HTTPException(409, "A superseded document cannot be made operative again")
    if verification_status == "VERIFIED_PRIMARY_SOURCE" and not doc.is_primary_source:
        raise HTTPException(422, "Only an original government publication can be verified as a primary source")
    operative = status in OPERATIVE_DOCUMENT_STATUSES
    if operative:
        if verification_status not in VERIFIED:
            raise HTTPException(422, "A document becomes operative only when it is verified")
        allowed = JURISDICTION_OPERATIVE if doc.society_id is None else STATUS_FOR_TYPE.get(doc.document_type)
        if not allowed or status not in allowed:
            raise HTTPException(422, f"A {doc.document_type.replace('_', ' ').lower()} cannot be recorded as "
                                     f"{status.replace('_', ' ').lower()}")
        markers = DRAFT_MARKERS.findall((doc.extracted_text or "")[:20000])
        if markers and not (override_draft_warning and len(override_draft_warning.strip()) >= 10):
            raise HTTPException(409, "The document text contains draft markers. Confirm this is the final registered "
                                     "version: give a reason (override_draft_warning) citing the registration details.")
        if doc.society_id and status in ("REGISTERED", "APPROVED_AMENDMENT") and not (approval_date or doc.approval_date):
            raise HTTPException(422, "Record the date the Registrar registered / approved it (approval_date)")
        if doc.extraction_quality in ("OCR_REQUIRED", "NONE") and not note:
            raise HTTPException(422, "The text could not be extracted; record in the note how the content was verified")
    for k, v in (("issue_date", issue_date), ("approval_date", approval_date), ("effective_from", effective_from),
                 ("effective_until", effective_until)):
        if v is not None:
            setattr(doc, k, v)
    doc.status, doc.verification_status, doc.verification_note = status, verification_status, note
    doc.verified_by, doc.verified_at = user.id, datetime.utcnow()
    if status == "REGISTERED" and doc.document_type == "REGISTERED_BYELAWS" and doc.society_id:
        _supersede_previous_bylaws(db, doc, user)
    if status == "APPROVED_AMENDMENT" and doc.society_id:
        prof = db.query(LegalProfile).filter(LegalProfile.society_id == doc.society_id).first()
        if prof:
            prof.approved_amendments = sorted(set((prof.approved_amendments or []) + [str(doc.id)]))
    for r in db.query(LegalReview).filter(LegalReview.dedupe_key == f"document:{doc.id}",
                                          LegalReview.status.in_(("OPEN", "IN_REVIEW"))):
        r.status, r.decided_by, r.decided_at, r.decision, r.decision_note = (
            "RESOLVED", user.id, datetime.utcnow(), status, note)
    if doc.society_id:
        audit.record(db, doc.society_id, "legal_document_verified", "legal_document", doc.id, user.id,
                     {"status": status, "verification": verification_status})
    return doc


def _supersede_previous_bylaws(db: Session, doc: LegalDocument, user) -> None:
    for old in db.query(LegalDocument).filter(LegalDocument.society_id == doc.society_id, LegalDocument.id != doc.id,
                                              LegalDocument.document_type == "REGISTERED_BYELAWS",
                                              LegalDocument.status == "REGISTERED"):
        old.status, old.superseded_by_id = "SUPERSEDED", doc.id
        old.effective_until = (doc.effective_from or doc.approval_date or date.today())
    prof = db.query(LegalProfile).filter(LegalProfile.society_id == doc.society_id).first()
    if prof is None:
        prof = LegalProfile(society_id=doc.society_id)
        db.add(prof)
    prof.registered_bylaw_document_id = doc.id
    prof.registered_bylaw_version = doc.reference_number or (doc.approval_date.isoformat() if doc.approval_date else None)


def document_dict(d: LegalDocument, detail: bool = False) -> dict:
    out = {"id": str(d.id), "society_specific": d.society_id is not None, "jurisdiction": d.jurisdiction,
           "document_type": d.document_type, "source_level": d.source_level, "title": d.title,
           "source_authority": d.source_authority, "source_url": d.source_url, "is_primary_source": d.is_primary_source,
           "reference_number": d.reference_number, "file_name": d.file_name, "mime_type": d.mime_type,
           "size_bytes": d.size_bytes, "sha256": d.sha256, "language": d.language, "page_count": d.page_count,
           "extraction_method": d.extraction_method, "extraction_quality": d.extraction_quality,
           "extraction_issues": d.extraction_issues or [],
           "issue_date": d.issue_date.isoformat() if d.issue_date else None,
           "approval_date": d.approval_date.isoformat() if d.approval_date else None,
           "effective_from": d.effective_from.isoformat() if d.effective_from else None,
           "effective_until": d.effective_until.isoformat() if d.effective_until else None,
           "status": d.status, "requested_status": d.requested_status, "verification_status": d.verification_status,
           "operative": d.status in OPERATIVE_DOCUMENT_STATUSES and d.verification_status in VERIFIED,
           "verification_note": d.verification_note, "verified_at": d.verified_at.isoformat() if d.verified_at else None,
           "superseded_by_id": str(d.superseded_by_id) if d.superseded_by_id else None,
           "duplicate_of_id": str(d.duplicate_of_id) if d.duplicate_of_id else None,
           "created_at": d.created_at.isoformat()}
    if detail:
        out["pages"] = [{"page": p.get("page"), "chars": p.get("chars"), "text": (p.get("text") or "")[:20000]}
                        for p in (d.pages or [])][:500]
    return out


def clause_dict(c: LegalClause) -> dict:
    return {"id": str(c.id), "document_id": str(c.document_id), "clause_ref": c.clause_ref, "heading": c.heading,
            "page_number": c.page_number, "language": c.language, "text": c.text,
            "needs_verification": c.needs_verification, "verified": c.verified}
