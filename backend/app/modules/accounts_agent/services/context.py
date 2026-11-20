"""What a detector sees: one voucher, its lines and the society's own reference data — all loaded society-scoped."""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent.models.agent import AgentSettings
from app.modules.accounts_agent.services.learning import Profile, learnable

ZERO = Decimal("0.00")


def money(v) -> Decimal:
    return Decimal(str(v if v is not None else 0)).quantize(Decimal("0.01"))


@dataclass
class Draft:
    """A finding before it is stored."""
    rule_code: str
    category: str
    finding_class: str
    severity: str
    confidence: float
    title: str
    explanation: str
    expected: str = ""
    actual: str = ""
    recommended: str = ""
    evidence: dict = field(default_factory=dict)
    subject: str = ""            # distinguishes several findings of one rule on one voucher (a ledger, a pair)
    voucher_id: Optional[UUID] = None

    def dedupe_key(self, voucher_id) -> str:
        return f"{self.rule_code}:{voucher_id}:{self.subject}"[:200]


@dataclass
class Ctx:
    db: Session
    voucher: Voucher
    meta: Dict[UUID, dict]                 # this society's ledgers
    settings: AgentSettings
    profile: Profile
    event_type: str = "voucher.created"

    @property
    def entries(self):
        return self.voucher.entries

    @property
    def is_manual(self) -> bool:
        return self.voucher.source_type is None

    @property
    def total_dr(self) -> Decimal:
        return sum((money(e.debit) for e in self.entries), ZERO)

    @property
    def total_cr(self) -> Decimal:
        return sum((money(e.credit) for e in self.entries), ZERO)

    def name(self, account_id) -> str:
        return self.meta.get(account_id, {}).get("name", "an unknown ledger")

    def in_profile(self) -> bool:
        """Was this voucher already part of the learned baseline? (Then its own numbers must be left out of it.)"""
        run, v = self.profile.run, self.voucher
        return bool(run and learnable(v) and run.window_start <= v.voucher_date <= run.window_end
                    and v.created_at <= run.started_at)

    def statistical_ok(self) -> bool:
        """Statistical comparisons only make sense for a live, ordinary voucher."""
        v = self.voucher
        return learnable(v) or (v.approval_status == "pending" and not v.is_cancelled and v.reversal_of_id is None
                                and v.voucher_type != "closing")


def line_signature(e) -> tuple:
    return (str(e.account_id), str(money(e.debit)), str(money(e.credit)),
            str(e.flat_id or ""), str(e.vendor_id or ""))


def fingerprint(v: Voucher) -> str:
    """Stable identity of a voucher's accounting content (not its number): used to find duplicates."""
    body = [str(v.society_id), v.voucher_type, v.voucher_date.isoformat(), str(money(v.amount)),
            sorted(line_signature(e) for e in v.entries), str(v.vendor_id or ""),
            (v.reference or "").strip().lower()]
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def state_fingerprint(v: Voucher) -> str:
    """Hash of everything a correction could depend on. A proposal stores it; if the voucher changes afterwards the
    hash differs and the proposal is refused as stale."""
    body = {
        "n": v.voucher_number, "d": v.voucher_date.isoformat(), "a": str(money(v.amount)), "t": v.voucher_type,
        "nar": v.narration or "", "ref": v.reference or "", "ven": str(v.vendor_id or ""),
        "c": bool(v.is_cancelled), "r": v.reversed_at.isoformat() if v.reversed_at else "",
        "s": v.approval_status, "e": v.edited_at.isoformat() if v.edited_at else "",
        "lines": sorted(line_signature(e) + (e.narration or "",) for e in v.entries),
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def fmt(amount) -> str:
    return f"₹{money(amount):,.2f}"


SNAPSHOT_KEY = "_voucher_at_detection"


def voucher_snapshot(db, voucher) -> Optional[dict]:
    """The voucher as it stood when a finding was raised (D-17 of the functional audit), so the finding can show the
    ORIGINAL evidence next to the voucher's current state after later edits. Ledger names are resolved now."""
    if voucher is None:
        return None
    from app.modules.accounts.models.accounts import Account
    names = dict(db.query(Account.id, Account.name).filter(Account.id.in_([e.account_id for e in voucher.entries])).all()) \
        if voucher.entries else {}
    return {"voucher_number": voucher.voucher_number, "voucher_date": voucher.voucher_date.isoformat(),
            "amount": str(money(voucher.amount)), "reference": voucher.reference, "narration": voucher.narration,
            "approval_status": voucher.approval_status, "is_cancelled": bool(voucher.is_cancelled),
            "entries": [{"account": names.get(e.account_id), "debit": str(money(e.debit)), "credit": str(money(e.credit))}
                        for e in sorted(voucher.entries, key=lambda x: x.line_no or 0)]}
