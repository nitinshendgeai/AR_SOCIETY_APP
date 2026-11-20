"""The Accounts Agent's analysis pipeline: voucher → drafts → stored findings. No financial record is ever modified."""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent.models.agent import (
    SEVERITY_RANK, AgentEvent, AgentFinding, AgentSettings, OPEN_FINDING_STATUSES,
)
from app.modules.accounts_agent.services import audit
from app.modules.accounts_agent.services.anomaly import STATISTICAL
from app.modules.accounts_agent.services.context import SNAPSHOT_KEY, Ctx, Draft, voucher_snapshot
from app.modules.accounts_agent.services.learning import Profile, account_meta
from app.modules.accounts_agent.services.rules import DETERMINISTIC

logger = logging.getLogger(__name__)

ANALYSED_EVENTS = ("voucher.created", "voucher.edited", "voucher.approval_changed")


def get_settings(db: Session, society_id: UUID) -> AgentSettings:
    """The society's settings, created with defaults on first use."""
    s = db.query(AgentSettings).filter(AgentSettings.society_id == society_id).first()
    if s is None:
        try:
            with db.begin_nested():
                s = AgentSettings(society_id=society_id)
                db.add(s)
                db.flush()
        except IntegrityError:               # another request created it first
            s = db.query(AgentSettings).filter(AgentSettings.society_id == society_id).one()
    return s


def load_voucher(db: Session, society_id: UUID, voucher_id: UUID, lock: bool = False) -> Optional[Voucher]:
    """The voucher, only if it belongs to `society_id` (society isolation for every agent read). With `lock`, the voucher
    row is held FOR UPDATE until the transaction ends (PostgreSQL; SQLite serialises writers anyway)."""
    q = (db.query(Voucher).options(selectinload(Voucher.entries))
         .filter(Voucher.id == voucher_id, Voucher.society_id == society_id))
    if lock and db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update(of=Voucher)
    return q.first()


def analyse(db: Session, voucher: Voucher, event_type: str = "voucher.created",
            settings: Optional[AgentSettings] = None, profile: Optional[Profile] = None) -> List[Draft]:
    """All findings for one voucher. A detector that crashes is logged and skipped; it never stops the others."""
    settings = settings or get_settings(db, voucher.society_id)
    profile = profile or Profile(db, voucher.society_id)
    c = Ctx(db=db, voucher=voucher, meta=account_meta(db, voucher.society_id), settings=settings, profile=profile,
            event_type=event_type)
    drafts: List[Draft] = []
    for fn in DETERMINISTIC:
        try:
            drafts += fn(c)
        except Exception:  # noqa: BLE001
            logger.exception("[accounts-agent] rule %s failed society=%s", fn.__name__, voucher.society_id)
    if c.statistical_ok():
        for fn in STATISTICAL:
            try:
                drafts += fn(c)
            except Exception:  # noqa: BLE001
                logger.exception("[accounts-agent] detector %s failed society=%s", fn.__name__, voucher.society_id)
    return drafts


def store_findings(db: Session, voucher: Voucher, drafts: List[Draft], profile_label: str,
                   event: Optional[AgentEvent] = None) -> List[AgentFinding]:
    """Persist drafts idempotently (unique per society + rule + voucher + subject). Returns only the NEW findings."""
    created: List[AgentFinding] = []
    existing = {k for (k,) in db.query(AgentFinding.dedupe_key).filter(AgentFinding.society_id == voucher.society_id,
                                                                       AgentFinding.voucher_id == voucher.id)}
    snap = None
    for d in drafts:
        key = d.dedupe_key(voucher.id)
        if key in existing:
            continue
        existing.add(key)
        if snap is None:
            snap = voucher_snapshot(db, voucher)
        d.evidence = {**(d.evidence or {}), SNAPSHOT_KEY: snap}
        f = AgentFinding(
            society_id=voucher.society_id, voucher_id=voucher.id, transaction_ref=voucher.voucher_number,
            voucher_date=voucher.voucher_date, category=d.category, finding_class=d.finding_class, severity=d.severity,
            confidence=d.confidence, rule_code=d.rule_code, dedupe_key=key, title=d.title[:200], explanation=d.explanation,
            expected_behaviour=d.expected, actual_behaviour=d.actual, evidence=d.evidence,
            recommended_action=d.recommended, status="NEW", learning_confidence=profile_label,
            source_event_id=event.id if event else None)
        try:
            with db.begin_nested():
                db.add(f)
                db.flush()
        except IntegrityError:                       # a concurrent worker stored it first: idempotent
            continue
        audit.record(db, voucher.society_id, "finding_created", "finding", f.id,
                     details={"rule": d.rule_code, "severity": d.severity, "voucher": voucher.voucher_number})
        created.append(f)
    return created


def _closing_note(f: AgentFinding, drafts: List[Draft], reason: str) -> str:
    """A duplicate pair that is still flagged under another duplicate rule was RE-CLASSIFIED, not cleared: say so."""
    if f.rule_code in DUPLICATE_RULES:
        subject = f.dedupe_key.split(":", 2)[2] if f.dedupe_key.count(":") >= 2 else ""
        other = next((d.rule_code for d in drafts if d.rule_code in DUPLICATE_RULES and d.subject == subject), None)
        if other:
            return f"Re-classified as {other} after the change; the pair is still flagged"
    return reason


def resolve_cleared(db: Session, voucher: Voucher, drafts: List[Draft], reason: str,
                    only_rules: Optional[tuple] = None, only_other: Optional[str] = None) -> int:
    """After an edit: open findings of this voucher whose rule no longer fires are closed — the agent re-verified.
    `only_rules` / `only_other` narrow it to the duplicate findings that name one particular partner voucher."""
    live = {d.dedupe_key(voucher.id) for d in drafts}
    n = 0
    q = db.query(AgentFinding).filter(AgentFinding.society_id == voucher.society_id, AgentFinding.voucher_id == voucher.id,
                                      AgentFinding.status.in_(("NEW", "UNDER_REVIEW")))
    if only_rules:
        q = q.filter(AgentFinding.rule_code.in_(only_rules))
    for f in q:
        if only_other and (f.evidence or {}).get("other_voucher_id") != only_other:
            continue
        if f.dedupe_key not in live:
            note = _closing_note(f, drafts, reason)
            f.status, f.resolved_at, f.resolution_note = "RESOLVED", datetime.utcnow(), note
            audit.record(db, f.society_id, "finding_auto_resolved", "finding", f.id, details={"reason": note})
            _stale_pending_proposals(db, f, note)
            n += 1
    return n


def _stale_pending_proposals(db: Session, f: AgentFinding, note: str) -> None:
    from app.modules.accounts_agent.models.agent import AgentProposal
    for p in db.query(AgentProposal).filter(AgentProposal.society_id == f.society_id, AgentProposal.finding_id == f.id,
                                            AgentProposal.status == "PENDING"):
        p.status, p.decided_at = "STALE", datetime.utcnow()
        p.decision_note = f"Not applied: the finding was closed ({note})."
        audit.record(db, p.society_id, "proposal_stale", "proposal", p.id, details={"reason": note})


def reanalyse_related(db: Session, changed: Voucher, settings: AgentSettings, profile: Profile) -> int:
    """A voucher changed. Duplicate findings are stored on the LATER voucher of a pair, so the partner of `changed`
    must be re-checked too: (a) vouchers whose open duplicate findings name `changed` as their twin, and (b) later
    vouchers that could now pair with it. Only the duplicate rules are re-run; nothing in the books changes."""
    from datetime import timedelta
    from app.modules.accounts_agent.services.rules import _order, check_duplicates
    ids = {f.voucher_id for f in db.query(AgentFinding).filter(
        AgentFinding.society_id == changed.society_id, AgentFinding.rule_code.in_(DUPLICATE_RULES),
        AgentFinding.voucher_id != changed.id, AgentFinding.status.in_(OPEN_FINDING_STATUSES))
        if (f.evidence or {}).get("other_voucher_id") == str(changed.id)}
    window = max(1, int(settings.duplicate_window_days))
    for o in (db.query(Voucher).filter(
            Voucher.society_id == changed.society_id, Voucher.id != changed.id, Voucher.is_cancelled == False,  # noqa: E712
            Voucher.voucher_type == changed.voucher_type, Voucher.amount == changed.amount,
            Voucher.voucher_date >= changed.voucher_date - timedelta(days=window),
            Voucher.voucher_date <= changed.voucher_date + timedelta(days=window)).limit(50)):
        if _order(o) > _order(changed):
            ids.add(o.id)
    n = 0
    meta = account_meta(db, changed.society_id)
    for vid in ids:
        r = load_voucher(db, changed.society_id, vid)
        if r is None:
            continue
        drafts = check_duplicates(Ctx(db=db, voucher=r, meta=meta, settings=settings, profile=profile,
                                      event_type="voucher.related_changed"))
        n += len(store_findings(db, r, drafts, profile.label))
        resolve_cleared(db, r, drafts, f"No longer detected after {changed.voucher_number} was changed",
                        only_rules=DUPLICATE_RULES, only_other=str(changed.id))
    return n


DUPLICATE_RULES = ("R-DUP-01", "R-DUP-02", "R-DUP-03", "R-DUP-04")


def resolve_twin_duplicates(db: Session, cancelled: Voucher) -> int:
    """A voucher was cancelled: open duplicate findings on OTHER vouchers that name it as their twin no longer hold
    (the pair is down to one live voucher). Close them and mark their pending proposals stale, so a second approval can
    never cancel the remaining, genuine voucher."""
    from app.modules.accounts_agent.models.agent import AgentProposal
    n = 0
    for f in db.query(AgentFinding).filter(AgentFinding.society_id == cancelled.society_id,
                                           AgentFinding.rule_code.in_(DUPLICATE_RULES),
                                           AgentFinding.voucher_id != cancelled.id,
                                           AgentFinding.status.in_(OPEN_FINDING_STATUSES)):
        if (f.evidence or {}).get("other_voucher_id") != str(cancelled.id):
            continue
        f.status, f.resolved_at = "RESOLVED", datetime.utcnow()
        f.resolution_note = f"Its duplicate {cancelled.voucher_number} was cancelled; this voucher is now the only copy"
        audit.record(db, f.society_id, "finding_auto_resolved", "finding", f.id,
                     details={"reason": "duplicate twin cancelled", "twin": cancelled.voucher_number})
        for p in db.query(AgentProposal).filter(AgentProposal.society_id == f.society_id, AgentProposal.finding_id == f.id,
                                                AgentProposal.status == "PENDING"):
            p.status, p.decided_at = "STALE", datetime.utcnow()
            p.decision_note = f"Not applied: its duplicate {cancelled.voucher_number} was already cancelled."
            audit.record(db, p.society_id, "proposal_stale", "proposal", p.id, details={"reason": "duplicate twin cancelled"})
        n += 1
    return n


def process_event(db: Session, event: AgentEvent) -> List[AgentFinding]:
    """Analyse one outbox event. Caller commits. Raises on failure so the worker can retry."""
    settings = get_settings(db, event.society_id)
    if not settings.monitoring_enabled:
        event.status, event.last_error = "skipped", "monitoring disabled"
        return []
    voucher = load_voucher(db, event.society_id, event.voucher_id)
    if voucher is None:
        event.status, event.last_error = "skipped", "voucher not found in this society"
        return []
    new: List[AgentFinding] = []
    if event.event_type == "voucher.cancelled":
        for f in db.query(AgentFinding).filter(AgentFinding.society_id == event.society_id, AgentFinding.voucher_id == voucher.id,
                                               AgentFinding.status.in_(("NEW", "UNDER_REVIEW"))):
            f.status, f.resolved_at, f.resolution_note = "RESOLVED", datetime.utcnow(), "Voucher was cancelled"
            audit.record(db, f.society_id, "finding_auto_resolved", "finding", f.id, details={"reason": "voucher cancelled"})
        resolve_twin_duplicates(db, voucher)
    elif event.event_type in ANALYSED_EVENTS and not (event.event_type == "voucher.approval_changed" and voucher.approval_status == "rejected"):
        profile = Profile(db, voucher.society_id)
        drafts = analyse(db, voucher, event.event_type, settings, profile)
        new = store_findings(db, voucher, drafts, profile.label, event)
        if event.event_type == "voucher.edited":
            resolve_cleared(db, voucher, drafts, "No longer detected after the voucher was edited")
            reanalyse_related(db, voucher, settings, profile)
    event.status, event.processed_at, event.last_error = "done", datetime.utcnow(), None
    settings.last_monitored_at, settings.last_error = datetime.utcnow(), None
    logger.info("[accounts-agent] event processed society=%s type=%s new_findings=%d", event.society_id, event.event_type, len(new))
    return new


def severity_at_least(sev: str, minimum: str) -> bool:
    return SEVERITY_RANK[sev] <= SEVERITY_RANK.get(minimum, 1)
