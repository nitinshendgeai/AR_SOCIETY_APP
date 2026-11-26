"""Whether a society's subscription includes AI, and how many tokens.

AI is part of the subscription, decided by the PLATFORM administrator, never by the society:

* an ACTIVE subscription that has not run out gets what its plan includes (Platform Console → AI plans) for each
  calendar month;
* a TRIAL that is still running gets the trial allowance, for the whole trial;
* an expired, suspended or cancelled society — or one whose paid period or trial has run out, even if nobody has
  marked it yet — gets no AI at all; the agent keeps answering from the bye-laws and the books;
* the platform administrator can switch AI on or off for one society, or give it its own allowance, whatever its plan.

The society's committee can only spend less: its own monthly budget (Learning & settings) is applied on top.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.society import AccountStatus, Society
from app.modules.accounts_agent.models.agent import AgentSettings, PlatformAiPlan

PLANS = ("trial", "starter", "growth", "enterprise")
PLAN_LABELS = {"trial": "Free trial", "starter": "Starter", "growth": "Growth", "enterprise": "Enterprise"}
# Used until the platform administrator saves the plan table (and in a database created without the migration seed).
DEFAULTS = {"trial": (True, 50_000), "starter": (False, 0), "growth": (True, 300_000), "enterprise": (True, 1_000_000)}


def plan_allowance(db: Session, plan_key: str) -> tuple:
    """(AI included, tokens) for one plan."""
    row = db.query(PlatformAiPlan).filter(PlatformAiPlan.plan_key == plan_key).first()
    if row is not None:
        return bool(row.ai_included), int(row.monthly_tokens or 0)
    return DEFAULTS.get(plan_key, (False, 0))


def plans(db: Session) -> list:
    return [{"plan_key": k, "label": PLAN_LABELS[k], "ai_included": inc, "tokens": n,
             "period": "trial" if k == "trial" else "month"}
            for k in PLANS for inc, n in [plan_allowance(db, k)]]


def entitlement(db: Session, society_id: UUID, settings: Optional[AgentSettings] = None,
                today: Optional[date] = None) -> dict:
    """{'allowed', 'tokens', 'period' ('month' | 'trial'), 'since' (trial start or None), 'plan', 'plan_label',
    'source' ('plan' | 'trial' | 'override'), 'reason'}"""
    society = db.get(Society, society_id)
    today = today or date.today()
    out = {"allowed": False, "tokens": 0, "period": "month", "since": None, "plan": None, "plan_label": None,
           "source": "plan", "reason": None}
    if society is None:
        return {**out, "reason": "No society."}
    status = society.account_status
    status = status.value if hasattr(status, "value") else str(status)
    override = (getattr(settings, "ai_plan_override", None) or "").lower() or None
    override_tokens = getattr(settings, "ai_override_tokens", None)

    if status == AccountStatus.TRIAL.value:
        if society.trial_end_date and society.trial_end_date < today:
            return {**out, "reason": "The free trial has ended. AI comes back when the society is put on a plan."}
        included, tokens = plan_allowance(db, "trial")
        out.update(plan="trial", plan_label=PLAN_LABELS["trial"], source="trial", period="trial",
                   since=society.trial_start_date)
    elif status == AccountStatus.ACTIVE.value:
        if society.subscription_expiry_date and society.subscription_expiry_date < today:
            return {**out, "plan": society.subscription_plan,
                    "reason": "The subscription has run out. AI comes back when it is renewed."}
        key = (society.subscription_plan or "").lower()
        included, tokens = plan_allowance(db, key)
        out.update(plan=key or None, plan_label=PLAN_LABELS.get(key, society.subscription_plan))
    else:
        word = {"EXPIRED": "has expired", "SUSPENDED": "is suspended", "CANCELLED": "is cancelled"}.get(status, status)
        return {**out, "plan": society.subscription_plan, "reason": f"The subscription {word}: AI is off."}

    if override == "off":
        return {**out, "source": "override", "reason": "AI is switched off for this society by DUX OS."}
    if override == "on":
        included = True
        out["source"] = "override"
    if override_tokens is not None:
        tokens = int(override_tokens)
        out["source"] = "override"
    if not included:
        return {**out, "reason": f"The {out['plan_label'] or 'current'} plan does not include AI. Ask DUX OS to add "
                                 f"it, or answers come from the bye-laws and books only."}
    return {**out, "allowed": tokens > 0, "tokens": tokens,
            "reason": None if tokens > 0 else "The AI allowance for this society is 0 tokens."}
