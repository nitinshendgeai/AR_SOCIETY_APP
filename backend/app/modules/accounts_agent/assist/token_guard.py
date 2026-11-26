"""Think twice before spending AI tokens.

Every place that could call the AI goes through here first:

1. **Reuse** — the same question on the same clauses was answered before: the kept answer is returned (no tokens).
2. **Subscription** — the society's plan must include AI (entitlement.py): an expired, suspended or cancelled
   subscription, an ended trial or a plan without AI means no request at all.
3. **Budget** — the plan's allowance (a month, or the whole trial) and the committee's own lower monthly budget
   (Accounts Agent → Learning & settings) must both have room: otherwise the app answers from its own data and says
   why.
3. **Record** — every request sent is counted with the tokens it actually used, and so is every request *not* sent
   (answered from the app's data, reused, or over budget), so the committee can see what the AI costs and saves.

Nothing here talks to the AI; it only decides and counts.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts_agent.assist import entitlement as plans
from app.modules.accounts_agent.models.agent import AgentAiAnswer, AgentAiUsage
from app.utils.local_time import society_today

FEATURES = {"bylaw_answer": "Bye-law answers", "entry_reading": "Reading entry descriptions"}
DEFAULT_BUDGET = 300_000
KEEP_FOR_DAYS = 90            # a kept answer older than this is asked afresh (the library may have been corrected)


def month_of(db: Session, society_id: UUID) -> str:
    return society_today(db, society_id).strftime("%Y-%m")


def _row(db: Session, society_id: UUID, feature: str) -> AgentAiUsage:
    month = month_of(db, society_id)
    row = (db.query(AgentAiUsage)
           .filter(AgentAiUsage.society_id == society_id, AgentAiUsage.month == month, AgentAiUsage.feature == feature)
           .first())
    if row is None:
        row = AgentAiUsage(society_id=society_id, month=month, feature=feature, ai_calls=0, input_tokens=0,
                           output_tokens=0, reused_answers=0, answered_locally=0, over_budget=0, not_included=0,
                           failed_calls=0)
        db.add(row)
        db.flush()
    return row


def spent_this_month(db: Session, society_id: UUID) -> int:
    month = month_of(db, society_id)
    total = (db.query(func.coalesce(func.sum(AgentAiUsage.input_tokens + AgentAiUsage.output_tokens), 0))
             .filter(AgentAiUsage.society_id == society_id, AgentAiUsage.month == month).scalar())
    return int(total or 0)


def spent_since(db: Session, society_id: UUID, since) -> int:
    """Tokens spent from the month of [since] on (a trial's allowance covers the whole trial)."""
    q = (db.query(func.coalesce(func.sum(AgentAiUsage.input_tokens + AgentAiUsage.output_tokens), 0))
         .filter(AgentAiUsage.society_id == society_id))
    if since is not None:
        q = q.filter(AgentAiUsage.month >= since.strftime("%Y-%m"))
    return int(q.scalar() or 0)


def check(db: Session, society_id: UUID, settings, estimate: int) -> tuple:
    """May a request of about [estimate] tokens be sent? (ok, counter to note when not, message for the reader)."""
    ent = plans.entitlement(db, society_id, settings, today=society_today(db, society_id))
    if not ent["allowed"]:
        return False, "not_included", (ent["reason"] or "AI is not part of this society's subscription.") + \
            " The clauses are listed without AI wording."
    if ent["period"] == "trial":
        if spent_since(db, society_id, ent["since"]) + max(0, estimate) > ent["tokens"]:
            return False, "over_budget", ("The free trial's AI allowance is used up, so the clauses are listed "
                                          "without AI wording. It comes back when the society is put on a plan.")
    elif spent_this_month(db, society_id) + max(0, estimate) > ent["tokens"]:
        return False, "over_budget", (f"This month's AI allowance in the {ent['plan_label']} plan is used up, so the "
                                      "clauses are listed without AI wording.")
    if not within_budget(db, society_id, settings, estimate):
        return False, "over_budget", ("This month's AI budget is used up, so the clauses are listed without AI "
                                      "wording. The committee can raise it in Accounts Agent → Learning & settings.")
    return True, None, None


def budget_of(settings) -> int:
    b = getattr(settings, "ai_monthly_token_budget", None)
    return DEFAULT_BUDGET if b is None else int(b)


def within_budget(db: Session, society_id: UUID, settings, estimate: int) -> bool:
    """True when [estimate] more tokens still fit in this month's budget. A budget of 0 means 'never call the AI'."""
    budget = budget_of(settings)
    return budget > 0 and spent_this_month(db, society_id) + max(0, estimate) <= budget


def estimate_tokens(*texts: str, reply: int = 600) -> int:
    """A rough count before sending (about 3.5 characters a token for English, fewer for Devanagari) plus the reply."""
    chars = sum(len(t or "") for t in texts)
    return int(chars / 3.0) + reply


def note(db: Session, society_id: UUID, feature: str, what: str) -> None:
    """Count a request that was NOT sent: what ∈ {'reused_answers', 'answered_locally', 'over_budget',
    'not_included'}."""
    row = _row(db, society_id, feature)
    setattr(row, what, (getattr(row, what) or 0) + 1)


def record_call(db: Session, society_id: UUID, feature: str, usage: Optional[dict], ok: bool) -> None:
    """Count a request that WAS sent, with the tokens the API reported (cache reads and writes included)."""
    row = _row(db, society_id, feature)
    row.ai_calls += 1
    if not ok:
        row.failed_calls += 1
    if usage:
        row.input_tokens += int(usage.get("input_tokens") or 0)
        row.output_tokens += int(usage.get("output_tokens") or 0)


def reuse(db: Session, society_id: UUID, feature: str, key: str) -> Optional[dict]:
    a = (db.query(AgentAiAnswer)
         .filter(AgentAiAnswer.society_id == society_id, AgentAiAnswer.feature == feature, AgentAiAnswer.key == key)
         .first())
    if a is None:
        return None
    if a.created_at and (datetime.utcnow() - a.created_at).days > KEEP_FOR_DAYS:
        db.delete(a)
        db.flush()
        return None
    a.hits = (a.hits or 0) + 1
    a.last_used_at = datetime.utcnow()
    return dict(a.payload or {})


def keep(db: Session, society_id: UUID, feature: str, key: str, payload: dict) -> None:
    a = (db.query(AgentAiAnswer)
         .filter(AgentAiAnswer.society_id == society_id, AgentAiAnswer.feature == feature, AgentAiAnswer.key == key)
         .first())
    if a is None:
        db.add(AgentAiAnswer(society_id=society_id, feature=feature, key=key, payload=payload, hits=0))
    else:
        a.payload = payload
    db.flush()


def forget_answers(db: Session, society_id: UUID) -> int:
    """Drop every kept answer (after the bye-laws in the library change)."""
    n = db.query(AgentAiAnswer).filter(AgentAiAnswer.society_id == society_id).delete(synchronize_session=False)
    db.flush()
    return int(n or 0)


def summary(db: Session, society_id: UUID, settings) -> dict:
    """This month's spend and savings, for the Learning & settings screen."""
    month = month_of(db, society_id)
    rows = (db.query(AgentAiUsage)
            .filter(AgentAiUsage.society_id == society_id, AgentAiUsage.month == month).all())
    by_feature = []
    totals = {k: 0 for k in ("ai_calls", "input_tokens", "output_tokens", "reused_answers", "answered_locally",
                             "over_budget", "not_included", "failed_calls")}
    for r in rows:
        d = {k: int(getattr(r, k) or 0) for k in totals}
        for k in totals:
            totals[k] += d[k]
        by_feature.append({"feature": r.feature, "label": FEATURES.get(r.feature, r.feature), **d})
    spent = totals["input_tokens"] + totals["output_tokens"]
    ent = plans.entitlement(db, society_id, settings, today=society_today(db, society_id))
    committee = budget_of(settings)
    if not ent["allowed"]:
        budget, period_spent = 0, spent
    elif ent["period"] == "trial":
        period_spent = spent_since(db, society_id, ent["since"])
        budget = min(committee, ent["tokens"]) if committee else 0
    else:
        period_spent = spent
        budget = min(committee, ent["tokens"])
    asked = (totals["ai_calls"] + totals["reused_answers"] + totals["answered_locally"] + totals["over_budget"]
             + totals["not_included"])
    without_ai = asked - totals["ai_calls"]
    kept = db.query(func.count(AgentAiAnswer.id)).filter(AgentAiAnswer.society_id == society_id).scalar() or 0
    return {"month": month, "budget_tokens": budget, "spent_tokens": period_spent, "spent_this_month": spent,
            "left_tokens": max(0, budget - period_spent),
            "used_pct": round(100 * period_spent / budget, 1) if budget else 0.0,
            "committee_budget": committee,
            "entitlement": {**ent, "since": ent["since"].isoformat() if ent["since"] else None},
            "requests": asked, "answered_without_ai": without_ai,
            "without_ai_pct": round(100 * without_ai / asked, 1) if asked else 0.0,
            "kept_answers": int(kept), **totals,
            "by_feature": sorted(by_feature, key=lambda x: x["feature"])}
