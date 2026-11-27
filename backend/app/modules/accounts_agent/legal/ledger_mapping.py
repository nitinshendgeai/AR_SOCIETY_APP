"""Which ledger each maintenance element is credited to — checked against the SOCIETY's own rules.

The app posts every bill line with one standard table (accounts/services/chart_of_accounts.py: bill_line_ledger_key /
ELEMENT_LEDGER), the same for every society. This module:

1. lets a society record its own element → ledger rule (a society LegalRule, topic "ledger.element.<code>", from its
   registered bye-laws or its approved accounting policy). Like every society rule it governs only once verified
   against an operative society document;
2. flags bills whose lines are credited to a ledger other than the society's verified rule says (A-LED-01), and lines
   that fall through to a default ledger because the charge head has no element, or its element is not in the standard
   table (A-LED-02 / A-LED-03);
3. builds the element → ledger map (element, standard ledger, society rule, ledger actually posted, source) for the
   committee or auditor to sign off; the sign-off records a fingerprint of the map, so a later change shows it as no
   longer signed off.

Nothing here changes the posting rules or any voucher: a difference is reported for a person to correct (normally by
changing the charge head's element in Billing, or the society's rule).
"""
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.modules.accounts.models.accounts import Account
from app.modules.accounts.services.chart_of_accounts import ELEMENT_LEDGER, bill_line_ledger_key
from app.modules.accounts_agent.legal import registry
from app.modules.accounts_agent.models.agent import AgentAuditLog
from app.modules.accounts_agent.services import audit
from app.modules.billing.models.billing import BillStatus, ChargeType, MaintenanceBill, MaintenanceChargeConfig

TOPIC_PREFIX = "ledger.element."
CALC_TYPE = "element_ledger"
RECENT_DAYS = 100
CATCH_ALL = "other_charges_recovered"
LIVE = (BillStatus.GENERATED, BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.PAID, BillStatus.OVERDUE)
SOURCE_LABELS = {"configured": "Set for this element by the society",
                 "special": "Fixed rule for interest / non-occupancy lines", "element": "Standard element table",
                 "keyword": "Recognised from the line's wording", "charge_type": "Default for the charge type (fallback)"}


def topic_for(element_code: str) -> str:
    return f"{TOPIC_PREFIX}{element_code}"


def ledger_source(charge_type, description: str, element_code: Optional[str]) -> tuple:
    """(ledger system key, how it was chosen). The key comes from the posting function itself, so this can never
    disagree with what is actually posted; the source label mirrors its order of decisions."""
    key = bill_line_ledger_key(SimpleNamespace(charge_type=charge_type, description=description), element_code)
    desc = (description or "").lower()
    if charge_type == ChargeType.PENALTY or "non-occupancy" in desc or "non occupancy" in desc:
        src = "special"
    elif element_code in ELEMENT_LEDGER:
        src = "element"
    elif "property tax" in desc or "municipal tax" in desc or ("transfer" in desc and "premium" in desc):
        src = "keyword"
    else:
        src = "charge_type"
    return key, src


def effective(by_id, by_key, charge_type, description: str, element) -> tuple:
    """(ledger Account or None, standard key or None, source) a bill line is ACTUALLY credited to — the same decision
    as posting: the ledger set for the element when there is one (never for interest / non-occupancy lines), else the
    standard table."""
    key, src = ledger_source(charge_type, description, element.code if element is not None else None)
    ledger_id = getattr(element, "credit_ledger_id", None)
    if ledger_id is not None and src != "special":
        acc = by_id.get(ledger_id)
        if acc is not None and acc.is_active:
            return acc, None, "configured"
    return by_key.get(key), key, src


def _accounts(db: Session, sid: UUID):
    rows = db.query(Account).filter(Account.society_id == sid).all()
    return {a.id: a for a in rows}, {a.system_key: a for a in rows if a.system_key}


def society_rule(db: Session, sid: UUID, element_code: str, on: date) -> registry.Applicable:
    return registry.resolve(db, sid, topic_for(element_code), on)


def _rule_account(app: registry.Applicable, by_id, by_key) -> Optional[Account]:
    if not app.rule:
        return None
    cm = app.rule.calculation_method or {}
    if cm.get("account_id"):
        try:
            return by_id.get(UUID(str(cm["account_id"])))
        except ValueError:
            return None
    return by_key.get(cm.get("ledger_key")) if cm.get("ledger_key") else None


def pending_rule(db: Session, sid: UUID, element_code: str):
    """The society's latest rule for this element that does not govern yet (unverified / document not operative)."""
    from app.modules.accounts_agent.legal.models import LegalRule
    return (db.query(LegalRule).filter(LegalRule.scope == str(sid), LegalRule.topic == topic_for(element_code),
                                       LegalRule.superseded_by_id.is_(None))
            .order_by(LegalRule.created_at.desc()).first())


def mapping(db: Session, sid: UUID, today: date) -> dict:
    """The element → ledger map of every active charge head, with what was actually posted recently."""
    by_id, by_key = _accounts(db, sid)
    heads = (db.query(MaintenanceChargeConfig).options(selectinload(MaintenanceChargeConfig.element))
             .filter(MaintenanceChargeConfig.society_id == sid, MaintenanceChargeConfig.is_active == True).all())  # noqa: E712
    heads = [h for h in heads if not (h.effective_to and h.effective_to < today)]
    posted = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    special = set()                       # interest / non-occupancy lines: posted by fixed rule, never a charge head
    for b in (db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
              .filter(MaintenanceBill.society_id == sid, MaintenanceBill.bill_status.in_(LIVE),
                      MaintenanceBill.bill_date >= today - timedelta(days=RECENT_DAYS))):
        for li in b.line_items:
            acc, key, src = effective(by_id, by_key, li.charge_type, li.description, _element_for(heads, li.description))
            posted[li.description][_key_of(acc, key)] += Decimal(str(li.amount))
            if src == "special":
                special.add(li.description)
    rows = []
    for h in sorted(heads, key=lambda h: h.name):
        code = h.element.code if h.element else None
        std, key, src = effective(by_id, by_key, h.charge_type, h.name, h.element)
        key = _key_of(std, key)
        app = society_rule(db, sid, code, today) if code else None
        rule_acc = _rule_account(app, by_id, by_key) if app else None
        pend = pending_rule(db, sid, code) if code and not (app and app.rule) else None
        status = "ok"
        if app and app.rule and rule_acc is None:
            status = "rule_ledger_missing"
        elif rule_acc is not None and std is not None and rule_acc.id != std.id:
            status = "differs_from_society_rule"
        elif code is None:
            status = "no_element"
        elif src == "charge_type":
            status = "fallback_ledger"
        rows.append({
            "charge_head_id": str(h.id), "charge_head": h.name,
            "charge_type": h.charge_type.value if hasattr(h.charge_type, "value") else str(h.charge_type),
            "element_code": code, "element": h.element.name if h.element else None,
            "posted_ledger_key": key, "posted_ledger": std.name if std else key, "posted_ledger_id": str(std.id) if std else None,
            "source": src, "source_label": SOURCE_LABELS[src],
            "society_rule": registry.source_ref(app.rule, app) if app and app.rule else None,
            "society_rule_ledger": rule_acc.name if rule_acc else None,
            "society_rule_ledger_id": str(rule_acc.id) if rule_acc else None,
            "pending_society_rule": registry.rule_dict(pend) if pend else None,
            "recent_postings": [{"ledger": _name(k, by_id, by_key), "amount": str(v)}
                                for k, v in posted.get(h.name, {}).items()],
            "status": status,
        })
    unmatched = [{"description": d, "ledgers": [{"ledger": _name(k, by_id, by_key), "amount": str(v)}
                                                for k, v in led.items()]}
                 for d, led in posted.items() if d not in {h.name for h in heads} and d not in special]
    fp = fingerprint(rows)
    signed = last_sign_off(db, sid)
    ledgers = [{"id": str(a.id), "name": a.name, "system_key": a.system_key, "nature": a.group.nature if a.group else None}
               for a in sorted(by_id.values(), key=lambda a: a.name)
               if a.is_active and a.group and a.group.nature in ("income", "liability")]
    return {"as_of": today.isoformat(), "rows": rows, "unmatched_bill_lines": unmatched, "fingerprint": fp,
            "signed_off": signed, "signed_off_current": bool(signed and signed["fingerprint"] == fp),
            "ledgers": ledgers,
            "note": "Bills are credited to the ledger set for each element (Accounts Agent → element review), else to "
                    "the app's standard element table. A society rule is what the agent checks against: apply it "
                    "with the element review, or revise the rule."}


def _key_of(acc, key) -> Optional[str]:
    """A stable key for the ledger a line goes to: its system key, else 'acc:<id>' (a ledger the society created)."""
    if acc is None:
        return key
    return acc.system_key or f"acc:{acc.id}"


def _name(k, by_id, by_key) -> str:
    if k in by_key:
        return by_key[k].name
    if isinstance(k, str) and k.startswith("acc:"):
        try:
            acc = by_id.get(UUID(k[4:]))
        except ValueError:
            acc = None
        return acc.name if acc is not None else k
    return k


def _element_for(heads, description: str):
    for h in heads:
        if h.name == description:
            return h.element
    return None


def _code_for(heads, description: str) -> Optional[str]:
    """The element code posting uses for a bill line: the element of the charge head with exactly that name."""
    for h in heads:
        if h.name == description:
            return h.element.code if h.element else None
    return None


def fingerprint(rows: List[dict]) -> str:
    essence = sorted((r["charge_head"], r["element_code"] or "", r["posted_ledger_key"], r["society_rule_ledger_id"] or "")
                     for r in rows)
    return hashlib.sha256(json.dumps(essence).encode()).hexdigest()


def last_sign_off(db: Session, sid: UUID) -> Optional[dict]:
    row = (db.query(AgentAuditLog).filter(AgentAuditLog.society_id == sid, AgentAuditLog.action == "ledger_map_signed_off")
           .order_by(AgentAuditLog.created_at.desc()).first())
    if row is None:
        return None
    d = row.details or {}
    return {"at": row.created_at.isoformat(), "by": str(row.actor_id) if row.actor_id else None,
            "role": d.get("role"), "note": d.get("note"), "fingerprint": d.get("fingerprint")}


def sign_off(db: Session, sid: UUID, user, role: str, note: str, expected_fingerprint: str, today: date) -> dict:
    """Record that the committee / auditor reviewed this exact map. Refused if the map changed since it was shown."""
    from fastapi import HTTPException
    current = mapping(db, sid, today)
    if current["fingerprint"] != expected_fingerprint:
        raise HTTPException(409, "The element → ledger map changed since it was shown; reload it and review again")
    audit.record(db, sid, "ledger_map_signed_off", "ledger_map", None, user.id,
                 {"fingerprint": current["fingerprint"], "role": role, "note": note[:500],
                  "rows": len(current["rows"]), "flagged": sum(1 for r in current["rows"] if r["status"] != "ok")})
    return current


# ── Compliance-scan checks ─────────────────────────────────────────────────────────────────────────────────────────

def _recent_lines(s):
    heads = [h for h in s.configs()]
    by_name = {h.name: h for h in heads}
    out = []
    for b in (s.db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
              .filter(MaintenanceBill.society_id == s.sid, MaintenanceBill.bill_status.in_(LIVE),
                      MaintenanceBill.bill_date >= s.today - timedelta(days=RECENT_DAYS))):
        for li in b.line_items:
            h = by_name.get(li.description)
            code = h.element.code if h and h.element else None
            out.append((b, li, h, code))
    return out


def chk_element_ledger_rules(s) -> List:
    """Bill lines credited to a ledger other than the society's verified element → ledger rule."""
    by_id, by_key = _accounts(s.db, s.sid)
    groups: Dict[tuple, dict] = {}
    for b, li, h, code in _recent_lines(s):
        if not code:
            continue
        app = s.rule(topic_for(code), b.bill_date)              # the rule in force on the bill's own date
        if not app.rule:
            continue
        want = _rule_account(app, by_id, by_key)
        got, _key, _src = effective(by_id, by_key, li.charge_type, li.description, h.element if h else None)
        if want is None or got is None or want.id == got.id:
            continue
        g = groups.setdefault((code, got.id, want.id), {"app": app, "want": want, "got": got, "bills": [], "amount": Decimal("0"),
                                                         "head": li.description})
        g["bills"].append(b.invoice_number)
        g["amount"] += Decimal(str(li.amount))
    out = []
    for (code, _g, _w), g in groups.items():
        app = g["app"]
        out.append(s.legal("A-LED-01", "element_ledger", "element_ledger", app,
                           f"'{g['head']}' is credited to {g['got'].name}; the society's rule says {g['want'].name}",
                           f"{len(g['bills'])} recent bill line(s) for '{g['head']}' (element {code}), {_inr(g['amount'])} in all, "
                           f"were credited to '{g['got'].name}'. The society's rule "
                           f"{app.rule.rule_code} ({registry.LEVEL_NAMES.get(app.rule.source_level)}) puts this element in "
                           f"'{g['want'].name}'.",
                           expected=g["want"].name, actual=g["got"].name, severity="MEDIUM",
                           recommended="If the society's rule is right, apply it in the agent's element review (Ledger map "
                                       "→ Review elements) so new bills follow it, and pass a journal moving the amounts "
                                       "already posted; if the current ledger is right, revise the society's rule.",
                           evidence={"element": code, "posted_ledger": g["got"].name, "rule_ledger": g["want"].name,
                                     "bills": g["bills"][:30], "amount": str(g["amount"])},
                           subject=f"{code}:{g['got'].id}"))
    return out


def chk_ledger_fallback(s) -> List:
    """Bill lines that land on a default ledger because their charge head has no element (or a non-standard one), and
    lines whose description matches no charge head (e.g. a head renamed after billing)."""
    from app.modules.accounts_agent.legal.compliance import LDraft
    _by_id, by_key = _accounts(s.db, s.sid)
    fallback: Dict[str, dict] = {}
    orphan: Dict[str, dict] = {}
    by_id = _by_id
    for b, li, h, code in _recent_lines(s):
        acc, key, src = effective(by_id, by_key, li.charge_type, li.description, h.element if h else None)
        if src != "charge_type":
            continue
        bucket = orphan if h is None else fallback
        g = bucket.setdefault(li.description, {"key": key, "bills": [], "amount": Decimal("0"), "code": code, "head": h})
        g["bills"].append(b.invoice_number)
        g["amount"] += Decimal(str(li.amount))
    out = []
    for desc, g in fallback.items():
        name = by_key[g["key"]].name if g["key"] in by_key else g["key"]
        catch_all = g["key"] == CATCH_ALL
        why = (f"its element '{g['code']}' is not in the standard element table" if g["code"]
               else "the charge head has no maintenance element linked")
        out.append(LDraft("A-LED-02", "accounting", "maintenance_billing", "element_ledger",
                          "SUSPECTED_ACCOUNTING_ANOMALY" if catch_all else "ADVISORY_OBSERVATION",
                          "MEDIUM" if catch_all else "LOW", 0.8 if catch_all else 0.5,
                          f"'{desc}' falls back to the default ledger '{name}'",
                          f"Recent bills credit '{desc}' ({_inr(g['amount'])} on {len(g['bills'])} line(s)) to '{name}' only because "
                          f"{why}, so the ledger is chosen from the charge type."
                          + (" 'Other Charges Recovered' is a catch-all: the income or fund this charge belongs to is hidden."
                             if catch_all else ""),
                          expected="Each charge head linked to its element and ledger", actual=f"Default: {name}",
                          recommended="Link the charge head to the right maintenance element in Billing, or record the "
                                      "society's element → ledger rule.",
                          evidence={"charge_head": desc, "element": g["code"], "ledger": name, "bills": g["bills"][:30],
                                    "amount": str(g["amount"])}, subject=desc[:120]))
    for desc, g in orphan.items():
        name = by_key[g["key"]].name if g["key"] in by_key else g["key"]
        out.append(LDraft("A-LED-03", "accounting", "maintenance_billing", "element_ledger", "SUSPECTED_ACCOUNTING_ANOMALY",
                          "MEDIUM", 0.75, f"Bill line '{desc}' matches no charge head and was posted to '{name}'",
                          f"{len(g['bills'])} recent bill line(s) described '{desc}' ({_inr(g['amount'])}) match no active charge "
                          "head, so posting could not find their element and used the charge type's default ledger. This "
                          "usually means a charge head was renamed or removed after the bills were made.",
                          recommended="Check the bills; restore the charge head's name or correct the postings by journal.",
                          evidence={"description": desc, "ledger": name, "bills": g["bills"][:30], "amount": str(g["amount"])},
                          subject=f"orphan:{desc}"[:120]))
    # Active charge heads with no element at all (even if not billed yet).
    billed = set(fallback) | set(orphan)
    for h in s.configs():
        if h.element_id is None and h.name not in billed and ledger_source(h.charge_type, h.name, None)[1] == "charge_type":
            key = ledger_source(h.charge_type, h.name, None)[0]
            out.append(LDraft("A-LED-04", "accounting", "maintenance_billing", "element_ledger", "ADVISORY_OBSERVATION", "LOW", 0.5,
                              f"Charge head '{h.name}' has no maintenance element",
                              f"When billed, '{h.name}' will be credited to the default ledger for its charge type "
                              f"('{by_key[key].name if key in by_key else key}').",
                              recommended="Link it to the right maintenance element in Billing.",
                              evidence={"charge_head": h.name, "default_ledger": key}, subject=str(h.id)))
    return out


def _inr(v) -> str:
    return f"₹{Decimal(str(v)).quantize(Decimal('0.01')):,.2f}"


CHECKS = [chk_element_ledger_rules, chk_ledger_fallback]
