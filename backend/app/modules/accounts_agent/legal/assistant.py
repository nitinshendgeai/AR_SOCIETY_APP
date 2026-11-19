"""A deterministic question-answering layer over the agent's own data. No language model and no paid API.

A question is matched to an intent by keywords; the answer is assembled ONLY from the society's books, its findings,
its resolutions and the legal rule registry. Every legal answer names the source, section/clause, effective date and
verification status, separates verified law from the society's own decisions, and states its uncertainty. When no
intent matches, it says so and lists what it can answer — it never invents a legal reference.
"""
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account, Voucher, VoucherEntry
from app.modules.accounts_agent.legal import calendar as cal
from app.modules.accounts_agent.legal import recovery, registry
from app.modules.accounts_agent.legal.models import ComplianceItem, SocietyResolution, VERIFIED
from app.modules.accounts_agent.models.agent import OPEN_FINDING_STATUSES, UNIFIED_CLASS, AgentFinding
from app.modules.billing.models.billing import MaintenanceSettings
from app.utils.local_time import society_today


def _findings(db, sid, rule_prefixes=(), categories=(), limit=10):
    q = db.query(AgentFinding).filter(AgentFinding.society_id == sid, AgentFinding.status.in_(OPEN_FINDING_STATUSES))
    rows = q.order_by(AgentFinding.created_at.desc()).all()
    out = [f for f in rows if (not rule_prefixes or f.rule_code.startswith(rule_prefixes))
           and (not categories or f.category in categories or f.compliance_category in categories)]
    return [{"id": str(f.id), "title": f.title, "severity": f.severity,
             "classification": UNIFIED_CLASS.get(f.finding_class, "ADVISORY_OBSERVATION")} for f in out[:limit]], len(out)


def _law(db, sid, topic, on):
    app = registry.resolve(db, sid, topic, on)
    return app, registry.source_ref(app.rule, app)


def _uncertainty(sources) -> str:
    unverified = [s for s in sources if s and not s.get("verified")]
    if not sources or all(s is None for s in sources):
        return "No legal rule in the registry covers this; the answer is based on the society's records only."
    if unverified:
        return ("The legal reference(s) used have not been verified against the original Gazette / registered bye-laws. "
                "Treat this as guidance for professional review, not a legal conclusion.")
    return "The legal reference(s) used are verified; applicability to your facts should still be confirmed."


def a_maintenance(db, sid, today):
    ms = db.query(MaintenanceSettings).filter(MaintenanceSettings.society_id == sid).first()
    (ia, isrc), (na, nsrc), (aa, asrc) = (_law(db, sid, t, today) for t in (
        "charges.interest_on_arrears.max_rate_pct", "charges.non_occupancy.max_pct", "charges.apportionment"))
    f, n = _findings(db, sid, ("L-CHG", "A-BIL", "L-FND"), ())
    lines = [f"{n} open finding(s) concern maintenance charges or billing." if n else
             "No open finding concerns maintenance charges or billing in the last scan."]
    if ms:
        lines.append(f"Interest on arrears is set to {ms.interest_rate_pct}% p.a. (ceiling on record: {ia.effective_value}% p.a.); "
                     f"non-occupancy {ms.non_occupancy_pct}% of service charges (ceiling on record: {na.effective_value}%).")
    lines.append("Each charge head's apportionment basis is compared with the apportionment rule; run a compliance scan "
                 "to refresh.")
    return " ".join(lines), [isrc, nsrc, asrc], {"findings": f}


def a_sinking(db, sid, today):
    acc = db.query(Account).filter(Account.society_id == sid, Account.system_key == "sinking_fund").first()
    if not acc:
        return "This society has no Sinking Fund ledger.", [], {}
    since = today - timedelta(days=365)
    rows = (db.query(Voucher.voucher_number, Voucher.voucher_date, VoucherEntry.debit, VoucherEntry.credit, Voucher.narration)
            .join(VoucherEntry, VoucherEntry.voucher_id == Voucher.id)
            .filter(Voucher.society_id == sid, VoucherEntry.account_id == acc.id, Voucher.is_cancelled == False,  # noqa: E712
                    Voucher.voucher_date >= since).order_by(Voucher.voucher_date).all())
    dr = sum((Decimal(str(r.debit)) for r in rows), Decimal("0"))
    cr = sum((Decimal(str(r.credit)) for r in rows), Decimal("0"))
    uses = [{"voucher": r.voucher_number, "date": r.voucher_date.isoformat(), "amount": str(r.debit), "narration": r.narration}
            for r in rows if r.debit]
    _, src = _law(db, sid, "funds.utilisation", today)
    f, _ = _findings(db, sid, ("L-FND", "A-FND"))
    text = (f"In the last 12 months the Sinking Fund received ₹{cr:,.2f} and ₹{dr:,.2f} was taken out of it "
            f"({len(uses)} withdrawal(s)). " + ("A decrease comes from these withdrawals; each is checked against the "
                                                 "resolution register." if uses else "Nothing was withdrawn."))
    return text, [src], {"withdrawals": uses, "findings": f}


def a_overdue(db, sid, today):
    rep = recovery.arrears(db, sid, today)
    d = [r for r in rep["flats"] if r["defaulter"]]
    text = (f"{len(rep['flats'])} flat(s) have unpaid bills totalling ₹{Decimal(rep['total_outstanding']):,.2f}; "
            f"{len(d)} are overdue beyond {rep['defaulter_after_months']} months. " + rep["note"])
    return text, [rep["rule"]], {"flats": rep["flats"][:50], "ageing_totals": rep["ageing_totals"]}


def a_vendor(db, sid, today):
    f, n = _findings(db, sid, ("L-EXP", "A-VEN"))
    _, src = _law(db, sid, "expenditure.committee_limit", today)
    text = (f"{n} open finding(s) concern vendor payments or their approval." if n else
            "No open finding questions a vendor payment's approval in the last scan.") + \
        (" Payments are compared with work-order sanctions, the resolution register and the committee's spending limit.")
    return text, [src], {"findings": f}


def a_fund_use(db, sid, today):
    app, src = _law(db, sid, "funds.utilisation", today)
    funds = (app.rule.calculation_method or {}).get("funds", {}) if app.rule else {}
    text = "; ".join(f"{k.replace('_', ' ').title()}: for {v.get('purpose')}, approval by the "
                     f"{v.get('authority', '').replace('_', ' ').lower()}" for k, v in funds.items()) or \
        "No fund-utilisation rule is in the registry."
    return ("Use of designated funds — " + text + ". A specific use needs a resolution recorded in the register."), [src], \
        {"funds": funds}


def a_non_occupancy(db, sid, today):
    app, src = _law(db, sid, "charges.non_occupancy.max_pct", today)
    ms = db.query(MaintenanceSettings).filter(MaintenanceSettings.society_id == sid).first()
    cm = (app.rule.calculation_method or {}) if app.rule else {}
    text = (f"Non-occupancy charges are worked out as a % of the flat's service charges ({cm.get('of', 'service charges')}), "
            f"capped at {app.effective_value}%. This society charges {ms.non_occupancy_pct if ms else 'no'}% (society "
            "decision recorded in Billing settings).")
    return text, [src], {"configured_pct": str(ms.non_occupancy_pct) if ms else None, "ceiling": app.effective_value}


def a_transfer(db, sid, today):
    app, src = _law(db, sid, "transfer.premium.max_amount", today)
    f, _ = _findings(db, sid, ("L-TRF",))
    text = (f"Transfer premium on record: ceiling ₹{app.effective_value:,} ({app.rule.rule_code if app.rule else 'no rule'}). "
            if app.effective_value else "No transfer-premium ceiling is in the registry. ") + \
        "Transfer premium credits are compared with it on each voucher."
    return text, [src], {"findings": f}


def a_approved_exceeded(db, sid, today):
    f, n = _findings(db, sid, ("L-EXP-RES", "L-EXP-WO-01", "L-FND-USE-02"))
    return ((f"{n} approval(s) appear to be exceeded." if n else "No approved amount is exceeded in the last scan.")
            + " Each is a potential issue until the resolution register and meeting records are checked."), [], {"findings": f}


def a_statutory(db, sid, today):
    cal.ensure_items(db, sid, today)
    rows = (db.query(ComplianceItem).filter(ComplianceItem.society_id == sid, ComplianceItem.completion_status == "PENDING")
            .order_by(ComplianceItem.due_date.is_(None), ComplianceItem.due_date).all())
    items = [cal.item_dict(r, today) for r in rows]
    pv = sum(1 for i in items if i["professional_verification_required"])
    text = (f"{len(items)} compliance item(s) are pending ({sum(1 for i in items if i['overdue'])} past their due date). "
            f"{pv} need professional verification of whether they apply at all.")
    return text, [], {"items": items}


def a_audit(db, sid, today):
    f, n = _findings(db, sid, ())
    return f"{n} finding(s) remain open (not resolved, rejected or ignored).", [], {"findings": f}


INTENTS: List[Tuple[str, re.Pattern, Callable]] = [
    ("sinking_fund_decrease", re.compile(r"sinking.*(decreas|reduc|less|down|fall|drop)|why.*sinking", re.I), a_sinking),
    ("fund_use", re.compile(r"(can|may|allowed).*(use|spend|utili[sz]).*fund|fund.*(for|use).*repair", re.I), a_fund_use),
    ("non_occupancy", re.compile(r"non[- ]?occupan", re.I), a_non_occupancy),
    ("transfer_fee", re.compile(r"transfer (fee|premium|charge)", re.I), a_transfer),
    ("approved_exceeded", re.compile(r"(approved|sanction).*(exceed|over|more)|exceed.*approv", re.I), a_approved_exceeded),
    ("vendor_approval", re.compile(r"vendor|contractor|payment.*approv", re.I), a_vendor),
    ("overdue", re.compile(r"overdue|outstanding|arrear|defaulter|dues", re.I), a_overdue),
    ("statutory", re.compile(r"statutory|compliance item|filing|return|gst|tds|agm|calendar", re.I), a_statutory),
    ("audit_open", re.compile(r"audit observation|unresolved|open finding|remain", re.I), a_audit),
    ("maintenance", re.compile(r"maintenance|charge|bill|interest", re.I), a_maintenance),
]
CAN_ANSWER = ["Is our maintenance calculation correct?", "Why has our sinking fund decreased?",
              "Are there overdue member payments?", "Is this vendor payment properly approved?",
              "Can our society use this fund for this repair?", "What is the applicable non-occupancy charge calculation?",
              "Which flats have outstanding dues?", "Is this transfer fee correctly calculated?",
              "Are any committee-approved amounts exceeded?", "What are our pending statutory compliance items?",
              "Which audit observations remain unresolved?"]


def ask(db: Session, society_id: UUID, question: str) -> dict:
    today = society_today(db, society_id)
    registry.ensure_jurisdiction_pack(db)
    for name, pat, fn in INTENTS:
        if pat.search(question or ""):
            text, sources, data = fn(db, society_id, today)
            sources = [s for s in sources if s]
            return {"intent": name, "answer": text, "sources": sources,
                    "verified_law": bool(sources) and all(s.get("verified") for s in sources),
                    "society_specific_sources": [s for s in sources if s.get("society_specific")],
                    "uncertainty": _uncertainty(sources), "data": data,
                    "disclaimer": "Generated from this society's records and the legal registry by fixed rules, not by "
                                  "an AI model. It is not legal advice and authorises no financial change."}
    return {"intent": None, "answer": "I can only answer questions about this society's accounts, funds, dues, approvals "
                                      "and compliance from its own records. Try one of the suggested questions.",
            "sources": [], "verified_law": False, "society_specific_sources": [], "uncertainty": None,
            "data": {"suggestions": CAN_ANSWER}, "disclaimer": None}
