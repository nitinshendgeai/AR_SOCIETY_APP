"""Learning: build a society's baseline from the most recent three months of its own books.

* The window is rolling: [today − 3 months, today] on the society's own clock, by voucher date.
* Only live vouchers count: approved, not cancelled, not reversed, not a reversal, not a year-end closing.
* Older vouchers are never read, changed or hidden — they simply aren't part of the baseline.
* Nothing is invented: with little data the run says so (confidence label "none"/"limited") and the detectors that need
  history stay silent.
* A profile is built from ONE society's rows only (every query filters society_id).
"""
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.modules.accounts.models.accounts import Account, AccountGroup, Voucher
from app.modules.accounts_agent.models.agent import AgentLearningRun, AgentPattern
from app.modules.accounts_agent.services import stats as st
from app.utils.local_time import society_today

logger = logging.getLogger(__name__)

WINDOW_MONTHS = 3
SAMPLE_CAP = 300                     # samples kept per pattern: enough for robust stats, bounded storage
MAX_PAIR_FANOUT = 6                  # a voucher with more debit/credit accounts than this is not pair-modelled


def months_before(d: date, months: int) -> date:
    y, m = d.year, d.month - months
    while m <= 0:
        y, m = y - 1, m + 12
    last = [31, 29 if (y % 4 == 0 and (y % 100 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, last))


def window_bounds(today: date) -> tuple:
    return months_before(today, WINDOW_MONTHS), today


def learnable(v: Voucher) -> bool:
    return (not v.is_cancelled and v.approval_status == "approved" and v.reversed_at is None
            and v.reversal_of_id is None and v.voucher_type != "closing")


def confidence(voucher_count: int, days_covered: int) -> tuple:
    """(score 0..1, label). Volume 60 %, time coverage 40 % — a society with ten vouchers in one week has a profile, but
    not a trustworthy one."""
    score = round(0.6 * min(1.0, voucher_count / 100) + 0.4 * min(1.0, days_covered / 84), 3)
    if voucher_count == 0:
        label = "none"
    elif voucher_count < 30 or days_covered < 45:
        label = "limited"
    elif voucher_count < 100 or days_covered < 75:
        label = "moderate"
    else:
        label = "good"
    return score, label


def account_meta(db: Session, society_id: UUID) -> Dict[UUID, dict]:
    rows = (db.query(Account.id, Account.name, Account.system_key, Account.is_cash, Account.is_bank, Account.is_active,
                     AccountGroup.nature, AccountGroup.name)
            .join(AccountGroup, AccountGroup.id == Account.group_id).filter(Account.society_id == society_id))
    return {r[0]: {"name": r[1], "system_key": r[2], "cash_bank": bool(r[3] or r[4]), "active": bool(r[5]),
                   "nature": r[6], "group": r[7]} for r in rows}


def _sample(v: Voucher, amount) -> list:
    return [str(v.id), float(amount), v.voucher_date.isoformat()]


def learn_society(db: Session, society_id: UUID, triggered_by: Optional[UUID] = None,
                  today: Optional[date] = None) -> AgentLearningRun:
    today = today or society_today(db, society_id)
    start, end = window_bounds(today)
    run = AgentLearningRun(society_id=society_id, window_start=start, window_end=end, status="running",
                           started_at=datetime.utcnow(), triggered_by=triggered_by)
    db.add(run)
    db.flush()
    try:
        meta = account_meta(db, society_id)
        vouchers: List[Voucher] = (db.query(Voucher).options(selectinload(Voucher.entries))
                                   .filter(Voucher.society_id == society_id, Voucher.voucher_date >= start,
                                           Voucher.voucher_date <= end, Voucher.is_cancelled == False)  # noqa: E712
                                   .order_by(Voucher.voucher_date).all())
        vouchers = [v for v in vouchers if learnable(v)]

        acct: Dict[str, list] = defaultdict(list)
        vend: Dict[str, dict] = {}
        pairs: Dict[str, int] = defaultdict(int)
        vtypes: Dict[str, dict] = {}
        rec: Dict[str, list] = defaultdict(list)
        line_count = 0

        for v in vouchers:
            vt = vtypes.setdefault(v.voucher_type, {"count": 0, "by_month": defaultdict(int), "amounts": []})
            vt["count"] += 1
            vt["by_month"][v.voucher_date.strftime("%Y-%m")] += 1
            vt["amounts"].append(_sample(v, v.amount))
            drs, crs = [], []
            for e in v.entries:
                line_count += 1
                dr, cr = float(e.debit or 0), float(e.credit or 0)
                if dr > 0:
                    acct[f"{e.account_id}:dr"].append(_sample(v, dr)); drs.append(str(e.account_id))
                if cr > 0:
                    acct[f"{e.account_id}:cr"].append(_sample(v, cr)); crs.append(str(e.account_id))
            if 0 < len(set(drs)) <= MAX_PAIR_FANOUT and 0 < len(set(crs)) <= MAX_PAIR_FANOUT:
                for d in set(drs):
                    for c in set(crs):
                        pairs[f"{v.voucher_type}|{d}|{c}"] += 1
            vendor_ids = {x for x in [v.vendor_id, *[e.vendor_id for e in v.entries]] if x}
            expense_accounts = [e.account_id for e in v.entries if float(e.debit or 0) > 0
                                and meta.get(e.account_id, {}).get("nature") == "expense"]
            for vid in vendor_ids:
                p = vend.setdefault(str(vid), {"amounts": [], "accounts": defaultdict(int)})
                p["amounts"].append(_sample(v, v.amount))
                for a in expense_accounts:
                    p["accounts"][str(a)] += 1
            if v.voucher_type in ("payment", "purchase", "journal") and expense_accounts:
                key = f"vendor:{next(iter(vendor_ids))}" if vendor_ids else f"account:{expense_accounts[0]}"
                rec[key].append(_sample(v, v.amount))

        patterns: List[AgentPattern] = []

        def add(ptype, key, n, data):
            patterns.append(AgentPattern(society_id=society_id, run_id=run.id, pattern_type=ptype, pattern_key=key[:200],
                                         sample_count=n, stats=data))

        for key, samples in acct.items():
            samples = samples[-SAMPLE_CAP:]
            add("account_amount", key, len(samples), {"samples": samples, **st.describe(s[1] for s in samples)})
        for vid, p in vend.items():
            samples = p["amounts"][-SAMPLE_CAP:]
            add("vendor", vid, len(samples), {"samples": samples, "accounts": dict(p["accounts"]),
                                              **st.describe(s[1] for s in samples)})
        for key, count in pairs.items():
            add("ledger_pair", key, count, {"count": count})
        for vt_name, vt in vtypes.items():
            samples = vt["amounts"][-SAMPLE_CAP:]
            add("voucher_type", vt_name, vt["count"], {"count": vt["count"], "by_month": dict(vt["by_month"]),
                                                       "samples": samples, **st.describe(s[1] for s in samples)})
        recurring_found = 0
        for key, samples in rec.items():
            months = {s[2][:7] for s in samples}
            # Recurring = roughly monthly: at least two months, and no more than ~1.5 postings per month on average
            # (frequent, variable spending such as stationery is not a recurring expense).
            if len(samples) >= 2 and len(months) >= 2 and len(samples) <= 1.5 * len(months):
                amounts = [s[1] for s in samples]
                days = [int(s[2][8:10]) for s in samples]
                recurring_found += 1
                add("recurring", key, len(samples), {
                    "samples": samples[-SAMPLE_CAP:], "months": sorted(months), "typical_day": int(st.med(days)),
                    **st.describe(amounts)})

        db.query(AgentPattern).filter(AgentPattern.society_id == society_id).delete(synchronize_session=False)
        db.flush()
        db.add_all(patterns)

        days_covered = ((vouchers[-1].voucher_date - vouchers[0].voucher_date).days + 1) if vouchers else 0
        score, label = confidence(len(vouchers), days_covered)
        run.voucher_count, run.line_count = len(vouchers), line_count
        run.months_covered = len({v.voucher_date.strftime("%Y-%m") for v in vouchers})
        run.days_covered, run.pattern_count = days_covered, len(patterns)
        run.confidence_score, run.confidence_label = score, label
        run.summary = {"voucher_types": {k: v["count"] for k, v in vtypes.items()}, "recurring_patterns": recurring_found,
                       "vendors": len(vend), "ledgers": len({k.split(":")[0] for k in acct}),
                       "note": ("Limited learning confidence: too little history in the window for reliable statistics."
                                if label in ("none", "limited") else None)}
        run.status, run.finished_at = "completed", datetime.utcnow()
        db.flush()
        logger.info("[accounts-agent] learning completed society=%s vouchers=%d patterns=%d confidence=%s",
                    society_id, len(vouchers), len(patterns), label)
        return run
    except Exception as exc:  # noqa: BLE001
        run.status, run.finished_at, run.error = "failed", datetime.utcnow(), str(exc)[:500]
        db.flush()
        logger.exception("[accounts-agent] learning failed society=%s", society_id)
        raise


class Profile:
    """Read access to a society's current learning profile (lazy, cached per instance, society-scoped)."""

    def __init__(self, db: Session, society_id: UUID):
        self.db, self.society_id = db, society_id
        self._cache: Dict[tuple, Optional[dict]] = {}
        self.run: Optional[AgentLearningRun] = (
            db.query(AgentLearningRun).filter(AgentLearningRun.society_id == society_id,
                                              AgentLearningRun.status == "completed")
            .order_by(AgentLearningRun.started_at.desc()).first())

    @property
    def label(self) -> str:
        return self.run.confidence_label if self.run else "none"

    def get(self, ptype: str, key: str) -> Optional[dict]:
        k = (ptype, key)
        if k not in self._cache:
            row = (self.db.query(AgentPattern.stats).filter(
                AgentPattern.society_id == self.society_id, AgentPattern.pattern_type == ptype,
                AgentPattern.pattern_key == key).first())
            self._cache[k] = row[0] if row else None
        return self._cache[k]

    def pairs_for(self, vtype: str) -> int:
        """How many distinct debit/credit combinations were seen for a voucher type."""
        n = (self.db.query(AgentPattern.id).filter(
            AgentPattern.society_id == self.society_id, AgentPattern.pattern_type == "ledger_pair",
            AgentPattern.pattern_key.like(f"{vtype}|%")).count())
        return n

    @staticmethod
    def others(samples: Optional[list], voucher_id) -> List[list]:
        """Samples without the voucher under analysis (leave-one-out, so it can't vouch for itself)."""
        return [s for s in (samples or []) if s[0] != str(voucher_id)]
