"""The Accounts Agent's review of the maintenance elements and their ledgers — and the fixes it may apply.

What a bill line is credited to, and which expense ledger belongs to which element, decide whether the society's books
follow its bye-laws. The agent checks every element of the society:

* **The society's own rule first** — when the society's registered bye-laws or approved accounting policy (a VERIFIED
  society rule in the Legal Library, topic "ledger.element.<code>") name the ledger, the element must credit it.
* **Funds are not income** — the sinking, repairs, reserve, contingency and education funds the bye-laws let a society
  collect (13(c), 67) are held for the members: they must be credited to a fund under "Reserve Fund & Other Funds",
  never to income. Charges recovered from members (service charges, water, electricity, taxes, parking…) are income.
* **No catch-all** — an element the standard table does not know (a society's own charge head) should credit its own
  ledger, not "Other Charges Recovered", where it disappears from the accounts.
* **Expense ledgers linked** — each standard expense ledger linked to the element it pays for (lift AMC → Lift
  Maintenance…), so payments are booked under the right head and spend per element can be shown.

Each finding comes with the exact change. Nothing is changed until an admin or committee member applies it (one tap
for the selected fixes); every change is audited, and affects bills generated from then on — bills already posted are
not rewritten (a journal moves those, if the committee wants).
"""
import hashlib
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.society import Society  # noqa: F401  (relationship target)
from app.modules.accounts.models.accounts import Account, AccountGroup
from app.modules.accounts.services.chart_of_accounts import DEFAULT_ELEMENT_LINKS, ELEMENT_LEDGER, CHARGE_TYPE_LEDGER
from app.modules.accounts_agent.legal import ledger_mapping
from app.modules.accounts_agent.services import audit
from app.modules.billing.models.billing import ChargeType, MaintenanceChargeConfig, MaintenanceElement

FUND_CODES = {"sinking_fund", "repair_fund", "reserve_fund", "contingency_fund", "education_fund", "major_repair_fund",
              "building_fund"}
FUND_CATEGORIES = {ChargeType.SINKING_FUND, ChargeType.REPAIR_FUND}
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _is_fund(e: MaintenanceElement) -> bool:
    return e.code in FUND_CODES or e.category in FUND_CATEGORIES or "fund" in (e.name or "").lower()


def _id(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _nature(acc: Optional[Account]) -> Optional[str]:
    return acc.group.nature if acc is not None and acc.group is not None else None


def _group_of(acc: Optional[Account]) -> Optional[str]:
    return acc.group.system_key if acc is not None and acc.group is not None else None


def _accounts(db: Session, sid: UUID):
    rows = db.query(Account).filter(Account.society_id == sid).all()
    return {a.id: a for a in rows}, {a.system_key: a for a in rows if a.system_key}


def _by_name(by_id, name: str, nature: str) -> Optional[Account]:
    want = (name or "").strip().lower()
    for a in by_id.values():
        if a.is_active and a.name.strip().lower() == want and _nature(a) == nature:
            return a
    return None


def review(db: Session, sid: UUID, today) -> dict:
    """Every finding about the elements and their ledgers, each with the change that fixes it."""
    by_id, by_key = _accounts(db, sid)
    elements = (db.query(MaintenanceElement).filter(MaintenanceElement.society_id == sid)
                .order_by(MaintenanceElement.sort_order, MaintenanceElement.name).all())
    used = {e_id for (e_id,) in db.query(MaintenanceChargeConfig.element_id)
            .filter(MaintenanceChargeConfig.society_id == sid, MaintenanceChargeConfig.is_active == True,  # noqa: E712
                    MaintenanceChargeConfig.element_id.isnot(None))}
    recs: List[dict] = []
    rows: List[dict] = []
    for e in elements:
        fund = _is_fund(e)
        want_nature = "liability" if fund else "income"
        current, _key, src = ledger_mapping.effective(by_id, by_key, e.category, e.name, e)
        app = ledger_mapping.society_rule(db, sid, e.code, today)
        rule_acc = ledger_mapping._rule_account(app, by_id, by_key) if app.rule else None
        ref = e.bye_law_ref or ("Bye-laws 13(c), 67" if fund else "Bye-laws 66–67")
        base = {"element_id": str(e.id), "element_code": e.code, "element": e.name, "in_use": e.id in used,
                "current_ledger": current.name if current else None, "bye_law_ref": ref}
        rows.append({**base, "kind": "fund" if fund else "recovery", "source": ledger_mapping.SOURCE_LABELS.get(src, src),
                     "ledger_nature": _nature(current), "society_rule_ledger": rule_acc.name if rule_acc else None})

        def propose(kind, severity, title, detail, fix, proposed_name, ref=ref):
            recs.append({**base, "id": _id(kind, e.id, fix.get("account_id") or fix.get("name")), "kind": kind,
                         "severity": severity, "title": title, "detail": detail, "proposed_ledger": proposed_name,
                         "bye_law_ref": ref, "fix": fix})

        if rule_acc is not None and (current is None or rule_acc.id != current.id):
            propose("follow_society_rule", "MEDIUM",
                    f"'{e.name}' should credit '{rule_acc.name}', as the society's rule says",
                    f"The society's verified rule {app.rule.rule_code} puts '{e.name}' in '{rule_acc.name}'; bills now "
                    f"credit '{current.name if current else 'no ledger'}'.",
                    {"action": "set_ledger", "element_id": str(e.id), "account_id": str(rule_acc.id)}, rule_acc.name,
                    ref=f"{app.rule.rule_code} (society rule)")
            continue
        if rule_acc is not None:
            continue                                  # the society's own verified rule governs and is followed
        std_key = ELEMENT_LEDGER.get(e.code) or CHARGE_TYPE_LEDGER.get(e.category)
        std = by_key.get(std_key) if std_key else None
        if current is None or _nature(current) != want_nature:
            target = std if std is not None and _nature(std) == want_nature else _by_name(by_id, e.name, want_nature)
            what = "a fund held for the members" if fund else "a charge recovered from members"
            wrong = ("income: it would show as the society's surplus and be spent" if fund and _nature(current) == "income"
                     else f"a ledger of nature '{_nature(current) or 'none'}'")
            detail = (f"'{e.name}' is {what}, so it belongs under "
                      f"{'Reserve Fund & Other Funds' if fund else 'Income from Members'}; bills now credit "
                      f"'{current.name if current else 'no ledger'}', which is {wrong}.")
            if target is not None:
                propose("wrong_ledger_nature", "HIGH", f"'{e.name}' is credited to the wrong kind of ledger", detail,
                        {"action": "set_ledger", "element_id": str(e.id), "account_id": str(target.id)}, target.name)
            else:
                propose("wrong_ledger_nature", "HIGH", f"'{e.name}' is credited to the wrong kind of ledger", detail,
                        {"action": "create_and_set", "element_id": str(e.id), "name": e.name,
                         "group_key": "funds" if fund else "income_members"}, f"{e.name} (new ledger)")
            continue
        if src == "charge_type" and _key == ledger_mapping.CATCH_ALL:
            target = _by_name(by_id, e.name, want_nature)
            detail = (f"'{e.name}' is not in the standard element table, so its bill lines fall into the catch-all "
                      f"'{current.name}', where the amount cannot be told apart from other recoveries.")
            fix = ({"action": "set_ledger", "element_id": str(e.id), "account_id": str(target.id)} if target is not None
                   else {"action": "create_and_set", "element_id": str(e.id), "name": e.name,
                         "group_key": "funds" if fund else "income_members"})
            propose("own_ledger_needed", "MEDIUM", f"Give '{e.name}' its own ledger", detail, fix,
                    target.name if target is not None else f"{e.name} (new ledger)")

    elements_by_code = {e.code: e for e in elements}
    for key, code in DEFAULT_ELEMENT_LINKS.items():
        acc, el = by_key.get(key), elements_by_code.get(code)
        if acc is None or el is None or not acc.is_active or acc.maintenance_element_id is not None:
            continue
        recs.append({"id": _id("link_expense", acc.id, el.id), "kind": "link_expense", "severity": "LOW",
                     "element_id": str(el.id), "element_code": el.code, "element": el.name, "in_use": el.id in used,
                     "current_ledger": acc.name, "proposed_ledger": acc.name, "bye_law_ref": el.bye_law_ref,
                     "title": f"Link the expense ledger '{acc.name}' to '{el.name}'",
                     "detail": f"Payments booked to '{acc.name}' are what '{el.name}' recovers from members. Linked, the "
                               "agent books such payments under it and the spend for the element can be shown.",
                     "fix": {"action": "link_expense", "account_id": str(acc.id), "element_id": str(el.id)}})
    recs.sort(key=lambda r: (SEVERITY_ORDER[r["severity"]], not r["in_use"], r["element"] or ""))
    return {"as_of": today.isoformat(), "elements": rows, "recommendations": recs,
            "summary": {"elements": len(rows), "to_fix": len(recs),
                        "high": sum(1 for r in recs if r["severity"] == "HIGH")}}


def _new_ledger(db: Session, sid: UUID, name: str, group_key: str) -> Account:
    group = (db.query(AccountGroup).filter(AccountGroup.society_id == sid, AccountGroup.system_key == group_key).first())
    if group is None:
        raise HTTPException(409, f"The standard group '{group_key}' is missing from the chart of accounts.")
    taken = {n.lower() for (n,) in db.query(Account.name).filter(Account.society_id == sid)}
    final = name if name.lower() not in taken else f"{name} ({'Fund' if group_key == 'funds' else 'Recovered'})"
    acc = Account(society_id=sid, group_id=group.id, name=final[:150], is_active=True)
    db.add(acc)
    db.flush()
    return acc


def apply(db: Session, sid: UUID, ids: List[str], user, today) -> dict:
    """Apply the selected fixes (by id, from a fresh review — so a fix that no longer applies is skipped)."""
    current = {r["id"]: r for r in review(db, sid, today)["recommendations"]}
    done, skipped = [], []
    for rid in ids:
        r = current.get(rid)
        if r is None:
            skipped.append({"id": rid, "reason": "No longer needed or changed since it was shown"})
            continue
        fix = r["fix"]
        el = db.get(MaintenanceElement, UUID(fix["element_id"]))
        if el is None or el.society_id != sid:
            skipped.append({"id": rid, "reason": "Element not found"})
            continue
        if fix["action"] == "set_ledger":
            acc = db.get(Account, UUID(fix["account_id"]))
            if acc is None or acc.society_id != sid:
                skipped.append({"id": rid, "reason": "Ledger not found"})
                continue
            el.credit_ledger_id = acc.id
            what = f"'{el.name}' now credits '{acc.name}'"
        elif fix["action"] == "create_and_set":
            acc = _new_ledger(db, sid, fix["name"], fix["group_key"])
            el.credit_ledger_id = acc.id
            what = f"New ledger '{acc.name}' created; '{el.name}' now credits it"
        elif fix["action"] == "link_expense":
            acc = db.get(Account, UUID(fix["account_id"]))
            if acc is None or acc.society_id != sid:
                skipped.append({"id": rid, "reason": "Ledger not found"})
                continue
            acc.maintenance_element_id = el.id
            what = f"Expense ledger '{acc.name}' linked to '{el.name}'"
        else:
            skipped.append({"id": rid, "reason": "Unknown change"})
            continue
        done.append({"id": rid, "kind": r["kind"], "change": what})
    if done:
        audit.record(db, sid, "element_setup_applied", "maintenance_elements", None, user.id,
                     {"changes": [d["change"] for d in done]})
    db.flush()
    return {"applied": done, "skipped": skipped,
            "note": "Bills generated from now on follow these ledgers. Bills already posted are unchanged; pass a "
                    "journal to move earlier amounts if the committee wants the past corrected too."}
