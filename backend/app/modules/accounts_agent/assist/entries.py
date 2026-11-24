"""Accounting entries drafted by the Accounts Agent — for approval, never posted.

The user describes an entry (a sentence, a form, or both). The agent fills in the voucher: the ledger from the user's
own choice, else from what this vendor's payments were posted to in the books (the learned pattern), else from
Claude's reading of the sentence (checked against the society's own ledger list). The voucher is created through the
normal AccountsService with every accounting rule applied, and is ALWAYS saved as pending: it counts in the books only
after someone approves it through the usual voucher approval (whoever drafted it cannot approve it while another
admin or committee member exists).
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account, AccountGroup
from app.modules.accounts.services.accounts_service import AccountsService
from app.modules.accounts_agent.assist import claude
from app.modules.accounts_agent.services import audit
from app.modules.accounts_agent.services.learning import Profile
from app.utils.local_time import society_today

MONEY_KEYS = {"bank": "bank", "cash": "cash"}


def _uuid(v) -> Optional[UUID]:
    try:
        return UUID(str(v)) if v else None
    except (ValueError, TypeError):
        return None


def _money(v) -> Optional[Decimal]:
    if v in (None, ""):
        return None
    try:
        d = Decimal(str(v).replace(",", "").replace("₹", "").strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return d if d > 0 else None


def _ledgers(db: Session, society_id: UUID, natures) -> List[dict]:
    rows = (db.query(Account.id, Account.name).join(AccountGroup, AccountGroup.id == Account.group_id)
            .filter(Account.society_id == society_id, Account.is_active == True,  # noqa: E712
                    Account.is_cash == False, Account.is_bank == False,  # noqa: E712
                    AccountGroup.nature.in_(natures)).order_by(Account.name).all())
    return [{"id": str(i), "name": n} for i, n in rows]


def _vendors(db: Session, society_id: UUID) -> List[dict]:
    from app.modules.vendor.models.vendor import Vendor
    rows = (db.query(Vendor.id, Vendor.company_name).filter(Vendor.society_id == society_id,
                                                           Vendor.is_active == True)  # noqa: E712
            .order_by(Vendor.company_name).all())
    return [{"id": str(i), "name": n} for i, n in rows]


def _vendor_usual_ledger(db: Session, society_id: UUID, vendor_id: UUID) -> Optional[UUID]:
    stats = Profile(db, society_id).get("vendor", str(vendor_id))
    dist = {k: int(n) for k, n in ((stats or {}).get("accounts") or {}).items() if int(n) > 0}
    if not dist:
        return None
    top, n = max(dist.items(), key=lambda kv: kv[1])
    return _uuid(top) if n / sum(dist.values()) >= 0.6 else None


def prepare(db: Session, society_id: UUID, data: dict, settings) -> dict:
    """Work out the voucher. Returns the proposal (nothing saved)."""
    svc = AccountsService(db)
    chart = svc.ensure_chart(society_id)
    text = (data.get("text") or "").strip()
    basis: List[str] = []
    unclear: List[str] = []
    parsed = None
    if text and claude.enabled(settings):
        natures = ("expense", "income")
        parsed = claude.parse_entry_request(text, _ledgers(db, society_id, natures), _vendors(db, society_id),
                                            society_today(db, society_id).isoformat())
        if parsed:
            basis.append("Read from your description by Claude; check every field.")
            unclear = list(parsed.unclear)
    vtype = data.get("voucher_type") or (parsed.voucher_type if parsed else None) or "payment"
    if vtype not in ("payment", "receipt"):
        raise HTTPException(422, "The agent drafts payments and receipts; enter journals yourself.")
    amount = _money(data.get("amount")) or (_money(parsed.amount) if parsed else None)
    if amount is None:
        raise HTTPException(422, "Give the amount of the entry.")
    vdate = data.get("voucher_date")
    if not vdate and parsed and parsed.voucher_date:
        try:
            vdate = date.fromisoformat(parsed.voucher_date)
        except ValueError:
            vdate = None
    vdate = vdate or society_today(db, society_id)
    vendor_ids = {v["id"] for v in _vendors(db, society_id)}
    vendor_id = _uuid(data.get("vendor_id")) or (_uuid(parsed.vendor_id) if parsed else None)
    if vendor_id and str(vendor_id) not in vendor_ids:
        vendor_id = None
    if vendor_id and vtype != "payment":
        raise HTTPException(422, "Only a payment can be made to a vendor.")
    money_key = data.get("money_account") or (parsed.money_account if parsed else None) or "bank"
    money_acc = chart.get(MONEY_KEYS.get(money_key, "bank"))
    if money_acc is None:
        raise HTTPException(422, "The society has no bank/cash ledger set up.")

    natures = ("expense",) if vtype == "payment" else ("income",)
    allowed = {x["id"]: x["name"] for x in _ledgers(db, society_id, natures)}
    ledger_id = _uuid(data.get("ledger_id"))
    if ledger_id:
        if str(ledger_id) not in allowed:
            raise HTTPException(422, "Choose an active expense (payment) or income (receipt) ledger of this society.")
        basis.append("Ledger chosen by you.")
    elif vendor_id and (usual := _vendor_usual_ledger(db, society_id, vendor_id)) and str(usual) in allowed:
        ledger_id = usual
        basis.append("Ledger: where this vendor's payments were posted in the last three months.")
    elif parsed and _uuid(parsed.ledger_id) and parsed.ledger_id in allowed:
        ledger_id = _uuid(parsed.ledger_id)
        basis.append("Ledger suggested by Claude from your description.")
    if not ledger_id:
        raise HTTPException(422, "Choose the ledger for this entry (the agent could not tell it from the request).")

    narration = (data.get("narration") or (parsed.narration if parsed else None) or text or "")[:250] or None
    reference = (data.get("reference") or (parsed.reference if parsed else None) or None)
    if vtype == "payment":
        entries = [{"account_id": ledger_id, "debit": amount, "credit": Decimal("0")},
                   {"account_id": money_acc.id, "debit": Decimal("0"), "credit": amount}]
    else:
        entries = [{"account_id": money_acc.id, "debit": amount, "credit": Decimal("0")},
                   {"account_id": ledger_id, "debit": Decimal("0"), "credit": amount}]
    names = {**allowed, str(money_acc.id): money_acc.name}
    return {"voucher_type": vtype, "voucher_date": vdate, "amount": amount, "vendor_id": vendor_id,
            "narration": narration, "reference": reference, "entries": entries, "basis": basis, "unclear": unclear,
            "lines": [{"account_id": str(e["account_id"]), "account": names.get(str(e["account_id"])),
                       "debit": str(e["debit"]), "credit": str(e["credit"])} for e in entries]}


def draft(db: Session, society_id: UUID, user, data: dict, settings, save: bool) -> dict:
    p = prepare(db, society_id, data, settings)
    out = {k: (str(v) if isinstance(v, (Decimal, UUID, date)) else v) for k, v in p.items() if k != "entries"}
    out["saved"] = False
    if not save:
        return out
    svc = AccountsService(db)
    v = svc.create_manual_voucher({
        "society_id": society_id, "voucher_type": p["voucher_type"], "voucher_date": p["voucher_date"],
        "narration": p["narration"], "reference": p["reference"], "vendor_id": p["vendor_id"],
        "entries": p["entries"]}, user, keep_pending=True,
        approval_note="Drafted by the Accounts Agent: check it, then another admin or committee member approves it.")
    audit.record(db, society_id, "entry_drafted", "voucher", v.id, user.id,
                 {"voucher": v.voucher_number, "amount": str(v.amount), "basis": p["basis"]})
    db.commit()
    out.update({"saved": True, "voucher_id": str(v.id), "voucher_number": v.voucher_number,
                "approval_status": v.approval_status})
    return out
