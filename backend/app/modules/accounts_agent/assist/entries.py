"""Accounting entries drafted by the Accounts Agent — for approval, never posted.

The user describes an entry (a sentence, a form, or both). The agent fills in the voucher: the ledger from the user's
own choice, else from what this vendor's payments were posted to in the books (the learned pattern), else from
Claude's reading of the sentence (checked against the society's own ledger list). The voucher is created through the
normal AccountsService with every accounting rule applied, and is ALWAYS saved as pending: it counts in the books only
after someone approves it through the usual voucher approval (whoever drafted it cannot approve it while another
admin or committee member exists).

Tokens: the app reads the description itself first (amount, cash or bank, vendor, ledger, date, reference — in English,
Hindi or Marathi words). Claude is asked only when that leaves the amount or the ledger unknown, within the society's
monthly budget, and then gets only the likely ledgers and vendors, not the whole chart.
"""
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account, AccountGroup
from app.modules.accounts.services.accounts_service import AccountsService
from app.modules.accounts_agent.assist import claude, prompt_opt, token_guard
from app.modules.accounts_agent.services import audit
from app.modules.accounts_agent.services.learning import Profile
from app.utils.local_time import society_today

MONEY_KEYS = {"bank": "bank", "cash": "cash"}
FEATURE = "entry_reading"
AI_LIST_SIZE = 25             # ledgers and vendors sent to Claude: the likeliest ones only

_AMOUNT = re.compile(r"(?<![\w/-])(?:₹|rs\.?|inr|रु\.?|रुपये|रुपए)?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(k|thousand|हजार|hazar|"
                     r"lakh|lac|लाख)?(?![\w/-])", re.IGNORECASE)
_DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")
_REF = re.compile(r"\b(?:bill|invoice|inv|cheque|chq|ref|utr|receipt)\s*(?:no\.?|number|#)?\s*[:#-]?\s*"
                  r"([A-Z0-9][A-Z0-9/-]{2,})", re.IGNORECASE)
_RECEIPT_WORDS = {"received", "receive", "receipt", "collected", "credited", "from", "mila", "mile", "jama", "जमा",
                  "मिळाले", "मिला", "प्राप्त", "आले"}
_PAYMENT_WORDS = {"paid", "pay", "payment", "paying", "spent", "to", "diya", "dile", "bhara", "bharle", "bharla",
                  "दिए", "दिले", "दिला", "भरले", "भरला", "भुगतान", "खर्च"}
_CASH_WORDS = {"cash", "nakad", "nagad", "rokh", "रोख", "नकद", "नगद"}
_BANK_WORDS = {"bank", "upi", "neft", "rtgs", "imps", "cheque", "chq", "gpay", "phonepe", "paytm", "बँक", "बैंक"}
_ENTRY_STOP = {"the", "for", "and", "of", "to", "from", "by", "on", "in", "at", "paid", "received", "bill", "month",
               "expenses", "expense", "charges", "income", "account", "a/c", "ltd", "pvt", "services", "service"}


def read_locally(text: str, ledgers: List[dict], vendors: List[dict], today: date) -> dict:
    """What the description says, read by rules (no tokens). Only fields it is sure of are filled."""
    low = (text or "").lower()
    words = set(prompt_opt._WORD.findall(low))
    mapped = set()
    for w in words:
        mapped.update(prompt_opt.lookup(w))
    out: dict = {"unclear": []}
    amounts = []
    plain = _REF.sub(" ", _DATE.sub(" ", text or ""))     # a date or a bill number is not an amount
    for m in _AMOUNT.finditer(plain):
        digits = m.group(1).replace(",", "")
        if len(digits) > 10:
            continue
        try:
            v = Decimal(digits)
        except InvalidOperation:
            continue
        unit = (m.group(2) or "").lower()
        v *= 1000 if unit in ("k", "thousand", "हजार", "hazar") else (100000 if unit in ("lakh", "lac", "लाख") else 1)
        if v > 0:
            amounts.append(v)
    if len(set(amounts)) > 1:                            # "for Nov 2026": a year beside the amount is not one
        amounts = [a for a in amounts if not (a == a.to_integral() and 1990 <= a <= 2099)] or amounts
    if len(set(amounts)) == 1:
        out["amount"] = str(amounts[0])
    elif len(set(amounts)) > 1:
        out["unclear"].append("amount (more than one number in the description)")
    if words & _RECEIPT_WORDS and not words & {"paid", "pay", "payment", "diya", "दिए", "दिले", "भुगतान"}:
        out["voucher_type"] = "receipt"
    elif words & _PAYMENT_WORDS or "payment" in mapped:
        out["voucher_type"] = "payment"
    if words & _CASH_WORDS or "cash" in mapped:
        out["money_account"] = "cash"
    elif words & _BANK_WORDS or "bank" in mapped:
        out["money_account"] = "bank"
    if re.search(r"\b(yesterday|kal)\b|काल|कल", low):
        out["voucher_date"] = (today - timedelta(days=1)).isoformat()
    elif (m := _DATE.search(text or "")):
        d, mo, y = (int(x) for x in m.groups())
        y = y + 2000 if y < 100 else y
        try:
            out["voucher_date"] = date(y, mo, d).isoformat()
        except ValueError:
            pass
    if (m := _REF.search(text or "")):
        out["reference"] = m.group(1)[:100]

    def best(items: List[dict]) -> Optional[str]:
        scored = []
        for x in items:
            name = {w for w in prompt_opt._WORD.findall(str(x["name"]).lower()) if w not in _ENTRY_STOP and len(w) > 2}
            hit = len(name & (words | mapped))
            if hit:
                scored.append((hit, x["id"]))
        scored.sort(reverse=True)
        if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return scored[0][1]
        return None                                        # nothing, or a tie: not guessed
    out["vendor_id"] = best(vendors)
    out["ledger_id"] = best(ledgers)
    return out


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
    read_by = None
    if text:
        natures = ("expense", "income")
        ledgers, vendors = _ledgers(db, society_id, natures), _vendors(db, society_id)
        today = society_today(db, society_id)
        local = read_locally(text, ledgers, vendors, today)
        has_amount = bool(data.get("amount") or local.get("amount"))
        vendor_for_ledger = _uuid(data.get("vendor_id")) or _uuid(local.get("vendor_id"))
        has_ledger = bool(data.get("ledger_id") or local.get("ledger_id")
                          or (vendor_for_ledger and _vendor_usual_ledger(db, society_id, vendor_for_ledger)))
        if claude.enabled(settings):
            if has_amount and has_ledger:
                token_guard.note(db, society_id, FEATURE, "answered_locally")     # the app could read it: no tokens
            else:
                short_l = prompt_opt.rank_names(ledgers, text, AI_LIST_SIZE)
                short_v = prompt_opt.rank_names(vendors, text, AI_LIST_SIZE)
                estimate = token_guard.estimate_tokens(claude.ENTRY_SYSTEM,
                                                       claude.entry_prompt(text, short_l, short_v, today.isoformat()),
                                                       reply=claude.ENTRY_MAX_TOKENS // 2)
                if token_guard.within_budget(db, society_id, settings, estimate):
                    parsed = claude.parse_entry_request(text, short_l, short_v, today.isoformat())
                    token_guard.record_call(db, society_id, FEATURE, claude.take_usage(), ok=parsed is not None)
                    if parsed:
                        read_by = "Claude"
                        basis.append("Read from your description by Claude; check every field.")
                        unclear = list(parsed.unclear)
                else:
                    token_guard.note(db, society_id, FEATURE, "over_budget")
                    basis.append("This month's AI budget is used up: the description was read by the app only.")
        if parsed is None and any(local.get(k) for k in ("amount", "ledger_id", "vendor_id", "voucher_type")):
            parsed = claude.EntryParse(voucher_type=local.get("voucher_type") or "payment",
                                       amount=local.get("amount"), voucher_date=local.get("voucher_date"),
                                       vendor_id=local.get("vendor_id"), ledger_id=local.get("ledger_id"),
                                       money_account=local.get("money_account") or "bank",
                                       reference=local.get("reference"), narration=text[:250],
                                       unclear=local.get("unclear") or [])
            read_by = "the app"
            basis.append("Read from your description by the app (no AI); check every field.")
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
        basis.append(f"Ledger read from your description by {read_by or 'the app'}.")
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
