"""Legal & bye-law intelligence tables for the Accounts Agent.

Society scoping: every society-owned row carries `society_id`. Jurisdiction-level law (the Act, the Rules, gazette
notifications, Government Resolutions) is the same for every society in the jurisdiction, so those rows have
`society_id = NULL` and a `jurisdiction` code; every society in that jurisdiction may READ them, only a platform
administrator may create or verify them. A society's own bye-laws, resolutions and rules always carry its id and are
never visible to another society.

- LegalProfile       one row per society: registration, classification, size, governing bye-law version.
- LegalDocument      an uploaded source (original file + SHA-256 + extracted text by page). Uploading never makes a
                     document operative: an authorised person must verify it.
- LegalClause        a clause extracted from a document, with its page reference.
- LegalRule          the versioned legal rule registry. A change in a rate or provision is a NEW version; earlier
                     versions are kept (effective_until / superseded_by), never overwritten.
- LegalReview        a human legal review item (source conflict, Marathi/English discrepancy, numbering discrepancy,
                     document verification). A blocking review stops the rule it names from producing a confirmed
                     violation.
- SocietyResolution  structured AGM / SGM / Managing Committee resolutions (purpose, amount, vendor, period, quorum).
- BudgetLine         the approved budget per ledger per financial year (for budget-vs-actual analysis).
- ComplianceItem     the statutory compliance calendar (one row per requirement per period).
"""
from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

JURISDICTION_MH = "IN-MH"

# Part 3 — the source hierarchy. Recorded on every document and rule; applied with scope and applicability, never as a
# blind ranking (see registry.py).
SOURCE_LEVELS = {
    "A": "Legislation and statutory rules",
    "B": "Binding Government notifications, Government Resolutions and Registrar directions",
    "C": "Court and tribunal orders",
    "D": "Registered bye-laws and approved amendments",
    "E": "General Body resolutions",
    "F": "Managing Committee resolutions",
    "G": "Internal society policies and accounting procedures",
    "H": "Model bye-laws and advisory guidance",
}

LEGAL_STATUSES = ("BINDING", "CONDITIONAL", "ADVISORY", "MODEL_REFERENCE", "DRAFT", "UNVERIFIED", "SUPERSEDED")
VERIFICATION_STATUSES = ("VERIFIED_PRIMARY_SOURCE", "VERIFIED_SECONDARY_SOURCE", "PENDING_VERIFICATION",
                         "LEGAL_REVIEW_REQUIRED", "REJECTED_SOURCE")
VERIFIED = ("VERIFIED_PRIMARY_SOURCE", "VERIFIED_SECONDARY_SOURCE")

DOCUMENT_STATUSES = ("REGISTERED", "APPROVED_AMENDMENT", "GENERAL_BODY_APPROVED", "COMMITTEE_APPROVED", "DRAFT",
                     "UNVERIFIED", "SUPERSEDED", "REJECTED")
OPERATIVE_DOCUMENT_STATUSES = ("REGISTERED", "APPROVED_AMENDMENT", "GENERAL_BODY_APPROVED", "COMMITTEE_APPROVED")

# document_type → its place in the hierarchy and whether it belongs to the jurisdiction (NULL society) or a society.
DOCUMENT_TYPES = {
    "ACT": ("A", "jurisdiction"),
    "STATUTORY_RULES": ("A", "jurisdiction"),
    "GAZETTE_NOTIFICATION": ("A", "jurisdiction"),
    "GOVERNMENT_RESOLUTION": ("B", "jurisdiction"),
    "GOVERNMENT_ORDER": ("B", "either"),
    "REGISTRAR_CIRCULAR": ("B", "either"),
    "COURT_ORDER": ("C", "either"),
    "REGISTERED_BYELAWS": ("D", "society"),
    "BYELAW_AMENDMENT": ("D", "society"),
    "AGM_MINUTES": ("E", "society"),
    "SGM_MINUTES": ("E", "society"),
    "COMMITTEE_MINUTES": ("F", "society"),
    "BUDGET": ("E", "society"),
    "VENDOR_APPROVAL_POLICY": ("G", "society"),
    "ACCOUNTING_POLICY": ("G", "society"),
    "LEGAL_OPINION": ("G", "society"),
    "AUDIT_REPORT": ("G", "society"),
    "MODEL_BYELAWS": ("H", "jurisdiction"),
    "OTHER": ("G", "society"),
}

REVIEW_TYPES = ("SOURCE_CONFLICT", "LANGUAGE_DISCREPANCY", "NUMBERING_DISCREPANCY", "DOCUMENT_VERIFICATION",
                "RULE_VERIFICATION", "INTERPRETATION", "BYELAW_OVERRIDE_ATTEMPT")
REVIEW_STATUSES = ("OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED")
OPEN_REVIEW_STATUSES = ("OPEN", "IN_REVIEW")

MEETING_TYPES = ("AGM", "SGM", "COMMITTEE")
APPROVAL_AUTHORITIES = ("GENERAL_BODY", "MANAGING_COMMITTEE")
RESOLUTION_STATUSES = ("RECORDED", "VERIFIED", "SUPERSEDED", "REJECTED")
RESOLUTION_CATEGORIES = ("expense", "contract", "fund_utilisation", "fund_transfer", "budget", "charges", "recovery",
                         "borrowing", "policy", "other")

COMPLIANCE_CATEGORIES = ("FINANCIAL_STATEMENTS", "STATUTORY_AUDIT", "AUDIT_RECTIFICATION", "AGM", "REGISTRAR",
                         "INCOME_TAX", "TDS", "GST", "ELECTION", "OTHER")
APPLICABILITY = ("APPLICABLE", "NOT_APPLICABLE", "PROFESSIONAL_VERIFICATION_REQUIRED")
COMPLETION_STATUSES = ("PENDING", "COMPLETED", "NOT_APPLICABLE")


def _soc(nullable=False):
    return Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=nullable, index=True)


def _user():
    return Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class LegalProfile(Base, TimestampMixin):
    __tablename__ = "accounts_agent_legal_profiles"
    __table_args__ = (UniqueConstraint("society_id", name="uq_agent_legal_profile_society"),)

    society_id               = _soc()
    registration_number      = Column(String(100), nullable=True)
    society_name             = Column(String(255), nullable=True)
    registration_date        = Column(Date, nullable=True)
    classification           = Column(String(80), nullable=True)      # e.g. "Tenant Ownership Housing Society"
    society_type             = Column(String(40), nullable=False, default="housing")
    number_of_units          = Column(Integer, nullable=True)
    number_of_members        = Column(Integer, nullable=True)
    state                    = Column(String(100), nullable=True)
    district                 = Column(String(100), nullable=True)
    jurisdiction             = Column(String(20), nullable=False, default=JURISDICTION_MH)
    financial_year_start_month = Column(Integer, nullable=False, default=4)
    registered_bylaw_document_id = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_documents.id",
                                                                         ondelete="SET NULL"), nullable=True)
    registered_bylaw_version = Column(String(60), nullable=True)
    approved_amendments      = Column(JSON, nullable=True)            # [document ids]
    adopted_model_bylaw_version = Column(String(60), nullable=True)
    legal_verification_status = Column(String(30), nullable=False, default="PENDING_VERIFICATION")
    last_legal_review_date   = Column(Date, nullable=True)
    updated_by               = _user()


class LegalDocument(Base, TimestampMixin):
    __tablename__ = "accounts_agent_legal_documents"
    __table_args__ = (Index("ix_agent_legal_docs_scope", "society_id", "document_type", "status"),)

    society_id         = _soc(nullable=True)                        # NULL: jurisdiction-wide law
    jurisdiction       = Column(String(20), nullable=False, default=JURISDICTION_MH)
    document_type      = Column(String(40), nullable=False)
    source_level       = Column(String(1), nullable=False)          # A..H (SOURCE_LEVELS)
    title              = Column(String(300), nullable=False)
    source_authority   = Column(String(200), nullable=True)
    source_url         = Column(String(500), nullable=True)
    is_primary_source  = Column(Boolean, nullable=False, default=False)   # original government publication
    reference_number   = Column(String(120), nullable=True)         # registration / notification / resolution no.
    file_name          = Column(String(255), nullable=False)
    mime_type          = Column(String(120), nullable=False)
    size_bytes         = Column(Integer, nullable=False)
    data               = Column(LargeBinary, nullable=False)         # the original file, unchanged
    sha256             = Column(String(64), nullable=False, index=True)
    language           = Column(String(10), nullable=False, default="unknown")   # en | mr | mixed | unknown
    extracted_text     = Column(Text, nullable=True)
    pages              = Column(JSON, nullable=True)                 # [{"page": 1, "text": "...", "chars": 123}]
    page_count         = Column(Integer, nullable=True)
    extraction_method  = Column(String(30), nullable=True)           # pdftotext | docx-xml | text | none
    extraction_quality = Column(String(20), nullable=False, default="NONE")   # GOOD | POOR | OCR_REQUIRED | NONE
    extraction_issues  = Column(JSON, nullable=True)                 # [str]
    issue_date         = Column(Date, nullable=True)
    approval_date      = Column(Date, nullable=True)
    effective_from     = Column(Date, nullable=True)
    effective_until    = Column(Date, nullable=True)
    status             = Column(String(30), nullable=False, default="UNVERIFIED")
    requested_status   = Column(String(30), nullable=True)            # what the uploader said it is
    verification_status = Column(String(30), nullable=False, default="PENDING_VERIFICATION")
    verified_by        = _user()
    verified_at        = Column(DateTime, nullable=True)
    verification_note  = Column(Text, nullable=True)
    superseded_by_id   = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_documents.id", ondelete="SET NULL"),
                                nullable=True)
    duplicate_of_id    = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_documents.id", ondelete="SET NULL"),
                                nullable=True)
    uploaded_by        = _user()


class LegalClause(Base, TimestampMixin):
    __tablename__ = "accounts_agent_legal_clauses"

    document_id        = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_documents.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    society_id         = _soc(nullable=True)
    clause_ref         = Column(String(60), nullable=False)
    heading            = Column(String(300), nullable=True)
    page_number        = Column(Integer, nullable=True)
    language           = Column(String(10), nullable=False, default="unknown")
    text               = Column(Text, nullable=False)
    needs_verification = Column(Boolean, nullable=False, default=True)
    verified           = Column(Boolean, nullable=False, default=False)
    verified_by        = _user()


class LegalRule(Base, TimestampMixin):
    __tablename__ = "accounts_agent_legal_rules"
    __table_args__ = (
        UniqueConstraint("scope", "rule_code", "version", name="uq_agent_legal_rule_version"),
        Index("ix_agent_legal_rules_topic", "scope", "topic", "effective_from"),
    )

    scope              = Column(String(40), nullable=False)          # jurisdiction code, or the society id
    society_id         = _soc(nullable=True)                         # NULL: jurisdiction-wide
    rule_code          = Column(String(60), nullable=False, index=True)   # the stable rule_id across versions
    version            = Column(Integer, nullable=False, default=1)
    topic              = Column(String(80), nullable=False)           # what the rule governs, e.g. charges.interest.max_rate
    jurisdiction       = Column(String(20), nullable=False, default=JURISDICTION_MH)
    society_type       = Column(String(40), nullable=False, default="housing")
    rule_category      = Column(String(40), nullable=False)           # charges | funds | expenditure | recovery | ...
    title              = Column(String(300), nullable=False)
    source_level       = Column(String(1), nullable=False)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_documents.id", ondelete="SET NULL"),
                                nullable=True)
    source_document_title = Column(String(300), nullable=True)
    source_authority   = Column(String(200), nullable=True)
    act_section        = Column(String(60), nullable=True)
    rule_number        = Column(String(60), nullable=True)
    bye_law_number     = Column(String(60), nullable=True)
    clause_reference   = Column(String(120), nullable=True)
    page_number        = Column(String(30), nullable=True)
    original_text      = Column(Text, nullable=True)
    translated_text    = Column(Text, nullable=True)
    publication_date   = Column(Date, nullable=True)
    effective_from     = Column(Date, nullable=True)
    effective_until    = Column(Date, nullable=True)
    legal_status       = Column(String(20), nullable=False, default="UNVERIFIED")
    verification_status = Column(String(30), nullable=False, default="PENDING_VERIFICATION")
    applicability_conditions = Column(JSON, nullable=True)            # {"society_type": "housing", "min_members": ..}
    calculation_method = Column(JSON, nullable=True)                  # {"type": "max_pct", "value": 12, ...}
    validation_expression = Column(String(300), nullable=True)
    required_evidence  = Column(JSON, nullable=True)                  # [str]
    severity           = Column(String(16), nullable=False, default="MEDIUM")
    human_review_required = Column(Boolean, nullable=False, default=True)
    superseded_by_id   = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_rules.id", ondelete="SET NULL"),
                                nullable=True)
    last_verified_at   = Column(DateTime, nullable=True)
    verified_by        = _user()
    verification_note  = Column(Text, nullable=True)
    change_note        = Column(Text, nullable=True)
    created_by         = _user()


class LegalReview(Base, TimestampMixin):
    __tablename__ = "accounts_agent_legal_reviews"
    __table_args__ = (UniqueConstraint("scope", "dedupe_key", name="uq_agent_legal_review_dedupe"),)

    scope          = Column(String(40), nullable=False)
    society_id     = _soc(nullable=True)
    review_type    = Column(String(30), nullable=False)
    title          = Column(String(300), nullable=False)
    description    = Column(Text, nullable=False)
    rule_codes     = Column(JSON, nullable=True)
    document_ids   = Column(JSON, nullable=True)
    details        = Column(JSON, nullable=True)
    blocking       = Column(Boolean, nullable=False, default=True)
    status         = Column(String(16), nullable=False, default="OPEN", index=True)
    dedupe_key     = Column(String(200), nullable=False)
    decided_by     = _user()
    decided_at     = Column(DateTime, nullable=True)
    decision       = Column(String(40), nullable=True)
    decision_note  = Column(Text, nullable=True)


class SocietyResolution(Base, TimestampMixin):
    __tablename__ = "accounts_agent_resolutions"
    __table_args__ = (Index("ix_agent_resolutions_society", "society_id", "meeting_date"),)

    society_id         = _soc()
    resolution_number  = Column(String(60), nullable=False)
    meeting_type       = Column(String(12), nullable=False)
    meeting_date       = Column(Date, nullable=False)
    notice_date        = Column(Date, nullable=True)
    agenda             = Column(Text, nullable=True)
    attendance         = Column(Integer, nullable=True)
    quorum_required    = Column(Integer, nullable=True)
    votes_for          = Column(Integer, nullable=True)
    votes_against      = Column(Integer, nullable=True)
    votes_abstain      = Column(Integer, nullable=True)
    approval_authority = Column(String(24), nullable=False)
    category           = Column(String(24), nullable=False, default="other")
    purpose            = Column(Text, nullable=False)
    approved_amount    = Column(Numeric(14, 2), nullable=True)
    vendor_id          = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    account_id         = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    work_order_id      = Column(UUID(as_uuid=True), ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True)
    contract_id        = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="SET NULL"), nullable=True)
    conditions         = Column(Text, nullable=True)
    period_from        = Column(Date, nullable=True)
    period_to          = Column(Date, nullable=True)
    supporting_document_id = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_legal_documents.id",
                                                                   ondelete="SET NULL"), nullable=True)
    governance_resolution_id = Column(UUID(as_uuid=True), ForeignKey("meeting_resolutions.id", ondelete="SET NULL"),
                                      nullable=True)
    status             = Column(String(16), nullable=False, default="RECORDED")
    supersedes_id      = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_resolutions.id", ondelete="SET NULL"),
                                nullable=True)
    verified_by        = _user()
    verified_at        = Column(DateTime, nullable=True)
    created_by         = _user()


class BudgetLine(Base, TimestampMixin):
    __tablename__ = "accounts_agent_budget_lines"
    __table_args__ = (UniqueConstraint("society_id", "fiscal_year", "account_id", name="uq_agent_budget_line"),)

    society_id      = _soc()
    fiscal_year     = Column(String(7), nullable=False)
    account_id      = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    approved_amount = Column(Numeric(14, 2), nullable=False)
    resolution_id   = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_resolutions.id", ondelete="SET NULL"),
                             nullable=True)
    note            = Column(Text, nullable=True)
    updated_by      = _user()


class ComplianceItem(Base, TimestampMixin):
    __tablename__ = "accounts_agent_compliance_items"
    __table_args__ = (UniqueConstraint("society_id", "code", "financial_period", name="uq_agent_compliance_item"),)

    society_id          = _soc()
    code                = Column(String(60), nullable=False)
    title               = Column(String(300), nullable=False)
    category            = Column(String(30), nullable=False)
    legal_rule_code     = Column(String(60), nullable=True)
    legal_source        = Column(Text, nullable=True)
    applicability       = Column(String(40), nullable=False, default="PROFESSIONAL_VERIFICATION_REQUIRED")
    applicability_reason = Column(Text, nullable=True)
    responsible_role    = Column(String(60), nullable=True)
    financial_period    = Column(String(7), nullable=False)
    due_date            = Column(Date, nullable=True)
    due_date_basis      = Column(Text, nullable=True)
    supporting_documents = Column(JSON, nullable=True)
    completion_status   = Column(String(20), nullable=False, default="PENDING")
    completed_on        = Column(Date, nullable=True)
    evidence_ref        = Column(String(200), nullable=True)
    verification_status = Column(String(30), nullable=False, default="PENDING_VERIFICATION")
    updated_by          = _user()
