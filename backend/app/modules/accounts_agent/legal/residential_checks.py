"""Four residential-accounting checks run by the compliance scan:

- vendor bank-account changes (a classic payment-diversion risk);
- the ledger handover when a flat changes owner;
- parking: allotted slots against what was billed, and double allotments;
- members' advances that sit unused while the flat has unpaid bills.

They only read the books (plus the agent's own record of vendor bank details) and never change a bill, receipt,
vendor or voucher. Every finding is an accounting observation for a person to review — none of them is a legal
conclusion.
"""
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import or_

from app.modules.accounts_agent.legal.models import VendorBankRecord

D0 = Decimal("0")
BANK_FIELDS = ("bank_name", "bank_account", "bank_ifsc")
BANK_WATCH_DAYS = 180
HANDOVER_LOOKBACK_DAYS = 730
OLD_ADVANCE_DAYS = 180
TWO_WHEELERS = {"motorcycle", "scooter", "bicycle"}


def _money(v) -> Decimal:
    return Decimal(str(v if v is not None else 0)).quantize(Decimal("0.01"))


def _inr(v) -> str:
    return f"₹{_money(v):,.2f}"


# ── Vendor bank-account changes ────────────────────────────────────────────────────────────────────────────────────

def _norm(v: Optional[str], drop: str = " -") -> str:
    s = (v or "").strip().upper()
    for ch in drop:
        s = s.replace(ch, "")
    return s


def bank_fingerprint(bank_name, account, ifsc) -> Optional[str]:
    """SHA-256 of the normalised account number and IFSC — where the money actually goes. The bank's name is free text
    and is not part of it, so retyping "HDFC" as "HDFC Bank" is not a change. None when there are no bank details."""
    a, i = _norm(account), _norm(ifsc)
    if not (a or i):
        return None
    return hashlib.sha256(f"{a}|{i}".encode()).hexdigest()


def masked(bank_name, account, ifsc) -> dict:
    a = _norm(account)
    return {"bank": bank_name or None, "account": ("XXXX" + a[-4:]) if a else None, "ifsc": _norm(ifsc) or None}


def _audit_bank_changes(db, vendor_ids) -> Dict:
    """Bank-detail edits recorded by the vendor screen's audit trail: {vendor_id: [(at, user_id, old, new)]}. Looked up
    only by this society's own vendor ids (the audit table has no society column)."""
    from app.models.audit_log import AuditLog
    if not vendor_ids:
        return {}
    rows = (db.query(AuditLog).filter(AuditLog.module == "vendor", AuditLog.entity_type == "Vendor",
                                      AuditLog.entity_id.in_([str(v) for v in vendor_ids]))
            .order_by(AuditLog.created_at).all())
    out = defaultdict(list)
    for r in rows:
        new, old = r.new_values or {}, r.old_values or {}
        if not any(k in new for k in BANK_FIELDS):
            continue
        if all((old.get(k) or None) == (new.get(k) or None) for k in BANK_FIELDS if k in new):
            continue
        out[r.entity_id].append((r.created_at, r.user_id, old, new))
    return out


def record_vendor_banks(s) -> None:
    """Bring the agent's bank-detail history up to date: one row per distinct set of details a vendor has had."""
    from app.modules.vendor.models.vendor import Vendor
    vendors = s.db.query(Vendor).filter(Vendor.society_id == s.sid).all()
    audits = _audit_bank_changes(s.db, [v.id for v in vendors])
    now = datetime.utcnow()
    for v in vendors:
        fp = bank_fingerprint(v.bank_name, v.bank_account, v.bank_ifsc)
        rows = (s.db.query(VendorBankRecord).filter(VendorBankRecord.vendor_id == v.id, VendorBankRecord.society_id == s.sid)
                .order_by(VendorBankRecord.first_seen_at).all())
        history = audits.get(str(v.id), [])
        if not rows:
            # First time the agent looks: reconstruct recent changes from the audit trail, else take today as baseline.
            recent = [h for h in history if h[0] >= now - timedelta(days=BANK_WATCH_DAYS)]
            if recent:
                at, _uid, old, _new = recent[0]
                ofp = bank_fingerprint(old.get("bank_name"), old.get("bank_account"), old.get("bank_ifsc"))
                if ofp:
                    s.db.add(VendorBankRecord(society_id=s.sid, vendor_id=v.id, fingerprint=ofp, is_baseline=True,
                                              masked=masked(old.get("bank_name"), old.get("bank_account"), old.get("bank_ifsc")),
                                              first_seen_at=at - timedelta(seconds=1), source="audit_log"))
                for at, uid, old, new in recent:
                    merged = {k: (new[k] if k in new else old.get(k)) for k in BANK_FIELDS}
                    nfp = bank_fingerprint(merged["bank_name"], merged["bank_account"], merged["bank_ifsc"])
                    if nfp and nfp != ofp:
                        s.db.add(VendorBankRecord(society_id=s.sid, vendor_id=v.id, fingerprint=nfp, is_baseline=ofp is None,
                                                  masked=masked(merged["bank_name"], merged["bank_account"], merged["bank_ifsc"]),
                                                  first_seen_at=at, source="audit_log", changed_by=uid))
                        ofp = nfp
                s.db.flush()
                rows = (s.db.query(VendorBankRecord).filter(VendorBankRecord.vendor_id == v.id)
                        .order_by(VendorBankRecord.first_seen_at).all())
            if not rows and fp:
                s.db.add(VendorBankRecord(society_id=s.sid, vendor_id=v.id, fingerprint=fp, is_baseline=True,
                                          masked=masked(v.bank_name, v.bank_account, v.bank_ifsc), first_seen_at=now))
                s.db.flush()
                continue
        if fp and (not rows or rows[-1].fingerprint != fp):
            since = rows[-1].first_seen_at if rows else None
            who = next((uid for at, uid, _o, _n in reversed(history) if since is None or at >= since), None)
            at = next((at for at, _u, _o, _n in reversed(history) if since is None or at >= since), now)
            s.db.add(VendorBankRecord(society_id=s.sid, vendor_id=v.id, fingerprint=fp, is_baseline=not rows,
                                      masked=masked(v.bank_name, v.bank_account, v.bank_ifsc),
                                      first_seen_at=max(at, since + timedelta(seconds=1)) if since else at,
                                      source="audit_log" if who else "scan", changed_by=who))
            s.db.flush()


def chk_vendor_bank_changes(s) -> List:
    from app.modules.accounts.models.accounts import Voucher
    from app.modules.accounts_agent.legal.compliance import LDraft
    from app.modules.vendor.models.vendor import Vendor
    record_vendor_banks(s)
    out = []
    cutoff = datetime.utcnow() - timedelta(days=BANK_WATCH_DAYS)
    names = {v.id: v.company_name for v in s.db.query(Vendor).filter(Vendor.society_id == s.sid)}
    by_vendor = defaultdict(list)
    for r in (s.db.query(VendorBankRecord).filter(VendorBankRecord.society_id == s.sid)
              .order_by(VendorBankRecord.first_seen_at).all()):
        by_vendor[r.vendor_id].append(r)
    for vid, rows in by_vendor.items():
        for i, r in enumerate(rows):
            if i == 0 or r.is_baseline or r.first_seen_at < cutoff:
                continue
            prev = rows[i - 1]
            paid = (s.db.query(Voucher.voucher_number, Voucher.voucher_date, Voucher.amount)
                    .filter(Voucher.society_id == s.sid, Voucher.vendor_id == vid, Voucher.voucher_type == "payment",
                            Voucher.is_cancelled == False, Voucher.voucher_date >= r.first_seen_at.date())  # noqa: E712
                    .order_by(Voucher.voucher_date).all())
            changes_90d = sum(1 for x in rows[1:] if not x.is_baseline and abs((x.first_seen_at - r.first_seen_at).days) <= 90)
            total = sum((_money(p.amount) for p in paid), D0)
            name = names.get(vid, "a vendor")
            out.append(LDraft(
                "A-VEN-BANK-01", "accounting", "vendor_audit", "vendor_bank_change", "SUSPECTED_ACCOUNTING_ANOMALY",
                "HIGH" if paid or changes_90d > 1 else "MEDIUM", 0.8 if paid else 0.6,
                f"{name}'s bank account was changed on {r.first_seen_at:%d %b %Y}"
                + (f"; {_inr(total)} paid since" if paid else ""),
                f"{name}'s bank details changed from {prev.masked.get('account') or '—'} ({prev.masked.get('ifsc') or '—'}) to "
                f"{r.masked.get('account') or '—'} ({r.masked.get('ifsc') or '—'})"
                + (f", recorded by a user of this society" if r.changed_by else ", outside the vendor screen (import or direct edit)")
                + (f". {len(paid)} payment(s) totalling {_inr(total)} have been made since." if paid else ". No payment has been made since.")
                + (f" The details changed {changes_90d} times within 90 days." if changes_90d > 1 else "")
                + " A changed bank account is the usual route of payment fraud.",
                expected="Bank change confirmed with the vendor through a known contact, with a cancelled cheque on file",
                actual="Change not yet reviewed",
                recommended="Confirm the new account with the vendor on a phone number already on record (not one given with "
                            "the change), keep the cancelled cheque or bank letter, and have a second committee member approve.",
                evidence={"previous": prev.masked, "new": r.masked, "changed_at": r.first_seen_at.isoformat(),
                          "source": r.source, "changed_by_user_id": str(r.changed_by) if r.changed_by else None,
                          "payments_since": [{"voucher": p.voucher_number, "date": p.voucher_date.isoformat(),
                                              "amount": str(_money(p.amount))} for p in paid[:20]],
                          "changes_within_90_days": changes_90d},
                subject=str(r.id), vendor_id=vid))
    return out


# ── Ownership handover ─────────────────────────────────────────────────────────────────────────────────────────────

def ownership_transfers(s) -> List[dict]:
    """Recent changes of owner, per flat: from owner residents' move-out / move-in dates and ownership-transfer events."""
    from app.models.flat import Flat
    from app.models.occupancy_log import OccupancyEventType, OccupancyLog
    from app.models.resident import Resident, ResidentType
    from app.models.wing import Wing
    since = s.today - timedelta(days=HANDOVER_LOOKBACK_DAYS)
    owners = (s.db.query(Resident).join(Flat, Flat.id == Resident.flat_id).join(Wing, Wing.id == Flat.wing_id)
              .filter(Wing.society_id == s.sid, Resident.resident_type.in_((ResidentType.OWNER, ResidentType.CO_OWNER)))
              .all())
    by_flat = defaultdict(list)
    for r in owners:
        by_flat[r.flat_id].append(r)
    out, seen = [], set()
    for flat_id, rows in by_flat.items():
        movers = [r for r in rows if r.move_out_date]
        for old in movers:
            new = sorted([r for r in rows if r.id != old.id and r.move_in_date
                          and abs((r.move_in_date - old.move_out_date).days) <= 90
                          and (old.move_in_date is None or r.move_in_date >= old.move_in_date)],
                         key=lambda r: r.move_in_date)
            if not new:
                continue
            when = new[0].move_in_date
            if when < since or (flat_id, when) in seen:
                continue
            seen.add((flat_id, when))
            out.append({"flat_id": flat_id, "date": when, "previous_owner": old.full_name, "new_owner": new[0].full_name,
                        "previous_still_active": False})
        # A newer owner moved in while an earlier owner was never marked as moved out.
        dated = sorted([r for r in rows if r.move_in_date], key=lambda r: r.move_in_date)
        for a, b in zip(dated, dated[1:]):
            if a.move_out_date is None and b.move_in_date >= since and b.move_in_date > a.move_in_date \
                    and (flat_id, b.move_in_date) not in seen and a.resident_type == ResidentType.OWNER \
                    and b.resident_type == ResidentType.OWNER:
                seen.add((flat_id, b.move_in_date))
                out.append({"flat_id": flat_id, "date": b.move_in_date, "previous_owner": a.full_name,
                            "new_owner": b.full_name, "previous_still_active": True})
    for e in s.db.query(OccupancyLog).filter(OccupancyLog.society_id == s.sid,
                                             OccupancyLog.event_type == OccupancyEventType.OWNERSHIP_TRANSFER,
                                             OccupancyLog.event_date >= since):
        if not any(t["flat_id"] == e.flat_id and abs((t["date"] - e.event_date).days) <= 30 for t in out):
            out.append({"flat_id": e.flat_id, "date": e.event_date, "previous_owner": None, "new_owner": None,
                        "previous_still_active": False})
    return out


def chk_ownership_handover(s) -> List:
    from app.modules.accounts.models.accounts import Voucher, VoucherEntry
    from app.modules.accounts_agent.legal.compliance import LDraft, LIVE_BILL
    from app.modules.billing.models.billing import MaintenanceBill, OnlinePaymentSubmission, ReconciliationStatus
    from app.modules.billing.services.allocations import unapplied
    out = []
    premium = s.accounts.get("transfer_premium")
    for t in ownership_transfers(s):
        fid, when = t["flat_id"], t["date"]
        flat = s.flat_label(fid)
        who = (f" from {t['previous_owner']} to {t['new_owner']}" if t["previous_owner"] and t["new_owner"] else "")
        subject = f"{fid}:{when.isoformat()}"
        if t["previous_still_active"]:
            out.append(LDraft("A-HND-04", "accounting", "member_ledger", "ownership_transfer", "ADVISORY_OBSERVATION", "LOW", 0.5,
                              f"{flat}: a new owner moved in on {when:%d %b %Y} but the earlier owner is still on record",
                              f"{t['new_owner']} is recorded as owner of {flat} from {when:%d %b %Y}, while {t['previous_owner']} "
                              "has no move-out date. Bills, receipts and notices may be addressed to the wrong member.",
                              recommended="Record the earlier owner's move-out (transfer) date in Residents.",
                              evidence={"date": when.isoformat()}, subject=subject, flat_id=fid))
        old_bills = (s.db.query(MaintenanceBill).filter(MaintenanceBill.society_id == s.sid, MaintenanceBill.flat_id == fid,
                                                        MaintenanceBill.bill_status.in_(LIVE_BILL),
                                                        MaintenanceBill.outstanding > 0, MaintenanceBill.due_date < when).all())
        if old_bills:
            due = sum((_money(b.outstanding) for b in old_bills), D0)
            out.append(LDraft("A-HND-01", "accounting", "member_ledger", "ownership_transfer", "MISSING_DOCUMENTATION", "MEDIUM", 0.75,
                              f"{flat}: {_inr(due)} of dues from before the transfer on {when:%d %b %Y} are still unpaid",
                              f"The flat changed owner{who} on {when:%d %b %Y}. {len(old_bills)} bill(s) due before that date "
                              f"({', '.join(b.invoice_number for b in old_bills[:6])}) still show {_inr(due)} outstanding on the "
                              "flat's ledger, which the new owner now sees. A transfer normally settles the transferor's dues, or "
                              "the transferee undertakes them in writing.",
                              expected="Dues settled at transfer, or a recorded undertaking", actual=f"{_inr(due)} carried forward",
                              recommended="Record who is liable: recover from the previous owner, or file the new owner's "
                                          "undertaking with the transfer papers.",
                              evidence={"bills": [b.invoice_number for b in old_bills], "outstanding": str(due),
                                        "transfer_date": when.isoformat()}, subject=subject, flat_id=fid))
        subs = (s.db.query(OnlinePaymentSubmission).filter(OnlinePaymentSubmission.society_id == s.sid,
                                                           OnlinePaymentSubmission.flat_id == fid,
                                                           OnlinePaymentSubmission.is_active == True,  # noqa: E712
                                                           OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED,
                                                           OnlinePaymentSubmission.payment_date < when).all())
        left = sum((unapplied(x) for x in subs), D0)
        if left >= Decimal("1"):
            out.append(LDraft("A-HND-02", "accounting", "member_ledger", "ownership_transfer", "SUSPECTED_ACCOUNTING_ANOMALY", "MEDIUM", 0.7,
                              f"{flat}: the previous owner's advance of {_inr(left)} is still on the flat",
                              f"Payments made before the transfer on {when:%d %b %Y} leave {_inr(left)} not yet set off. That "
                              "credit belongs to the previous owner unless they agreed to pass it on; if it is set off against "
                              "the new owner's bills, the previous owner's money pays the new owner's dues.",
                              expected="Advance refunded or transferred with written consent", actual=f"{_inr(left)} unadjusted",
                              recommended="Refund the previous owner, or file their written consent to transfer the credit.",
                              evidence={"advance": str(_money(left)), "transfer_date": when.isoformat()}, subject=subject, flat_id=fid))
        if premium is not None:
            lo, hi = when - timedelta(days=120), when + timedelta(days=120)
            has_fee = (s.db.query(VoucherEntry.id).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                       .filter(Voucher.society_id == s.sid, Voucher.is_cancelled == False,  # noqa: E712
                               VoucherEntry.account_id == premium.id, VoucherEntry.credit > 0,
                               Voucher.voucher_date.between(lo, hi),
                               or_(VoucherEntry.flat_id == fid, Voucher.narration.ilike(f"%{flat.split('-')[-1]}%")))
                       .first())
            if not has_fee:
                out.append(LDraft("A-HND-03", "accounting", "member_ledger", "transfer_charges", "ADVISORY_OBSERVATION", "LOW", 0.4,
                                  f"{flat}: no transfer premium or fee recorded around the transfer on {when:%d %b %Y}",
                                  "No credit to the Transfer Premium ledger for this flat was found within four months of the "
                                  "transfer. Check whether the society's bye-laws provide for one and whether it was collected.",
                                  recommended="Record the transfer premium / fee received, or note why none was due.",
                                  evidence={"transfer_date": when.isoformat()}, subject=subject, flat_id=fid))
    return out


# ── Parking reconciliation ─────────────────────────────────────────────────────────────────────────────────────────

def _overlaps(a_start: date, a_end: Optional[date], b_start: date, b_end: Optional[date]) -> bool:
    return a_start <= (b_end or date.max) and b_start <= (a_end or date.max)


def _held_until(a) -> Optional[date]:
    """The last day an allotment was held: its end date, or the day it was released."""
    ends = [d for d in (a.end_date, a.released_at.date() if a.released_at else None) if d]
    return min(ends) if ends else None


def chk_parking(s) -> List:
    from app.models.vehicle import Vehicle
    from app.modules.accounts_agent.legal.compliance import LDraft, LIVE_BILL
    from app.modules.billing.models.billing import BillingCycle, ChargeBasis, ChargeType, MaintenanceBill
    from app.modules.parking.models.parking import AllocationStatus, ParkingAllocation, ParkingSlot
    from sqlalchemy.orm import selectinload
    out = []
    allocs = (s.db.query(ParkingAllocation).filter(ParkingAllocation.society_id == s.sid, ParkingAllocation.is_active == True,  # noqa: E712
                                                   ParkingAllocation.status != AllocationStatus.SUSPENDED).all())
    slots = {sl.id: sl for sl in s.db.query(ParkingSlot).filter(ParkingSlot.id.in_({a.slot_id for a in allocs}))} if allocs else {}
    # Double allotment: one slot held by two flats at the same time.
    by_slot = defaultdict(list)
    for a in allocs:
        if a.flat_id:
            by_slot[a.slot_id].append(a)
    for slot_id, rows in by_slot.items():
        rows.sort(key=lambda a: a.start_date)
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a.flat_id != b.flat_id and _overlaps(a.start_date, _held_until(a), b.start_date, _held_until(b)):
                    sl = slots.get(slot_id)
                    num = sl.slot_number if sl else "a slot"
                    out.append(LDraft("A-PRK-03", "accounting", "maintenance_billing", "parking", "SUSPECTED_ACCOUNTING_ANOMALY", "HIGH", 0.85,
                                      f"Parking slot {num} is allotted to two flats at once",
                                      f"Slot {num} is allotted to {s.flat_label(a.flat_id)} (from {a.start_date}) and to "
                                      f"{s.flat_label(b.flat_id)} (from {b.start_date}) for overlapping periods. Both may be "
                                      "billed for one slot, or one is using a slot it was never allotted.",
                                      recommended="Release the allotment that is no longer valid in Parking.",
                                      evidence={"slot": num, "allotments": [str(a.id), str(b.id)]},
                                      subject=f"{a.id}:{b.id}", flat_id=b.flat_id))
    for a in allocs:
        sl = slots.get(a.slot_id)
        if sl is not None and sl.society_id != s.sid:
            out.append(LDraft("A-PRK-04", "accounting", "maintenance_billing", "parking", "CONFIRMED_ACCOUNTING_ERROR", "CRITICAL", 1.0,
                              "A parking allotment points at another society's slot",
                              "An allotment of this society refers to a parking slot that belongs to a different society.",
                              recommended="Escalate: this is a data-isolation fault.", subject=str(a.id)))
    heads = [c for c in s.configs() if c.charge_type == ChargeType.PARKING and not c.parking_zone_id]
    paying = [c for c in heads if (c.basis.value if hasattr(c.basis, "value") else str(c.basis)) == ChargeBasis.PARKING.value]
    if not paying:
        if heads or not allocs:
            return out
        if any(a.status == AllocationStatus.ACTIVE and a.flat_id for a in allocs):
            out.append(LDraft("A-PRK-05", "accounting", "maintenance_billing", "parking", "ADVISORY_OBSERVATION", "LOW", 0.4,
                              "Parking slots are allotted but no parking charge is billed",
                              "Flats hold allotted slots, but there is no parking charge head. If the society charges for "
                              "parking (as resolved by the General Body), the charge is not reaching the bills.",
                              recommended="Add a parking charge head in Billing, or note that parking is free.", subject="no-head"))
        return out
    two_wheeler_rate = any(c.two_wheeler_rate is not None for c in paying)
    tw_flats = {fid for (fid, vt) in s.db.query(Vehicle.flat_id, Vehicle.vehicle_type).filter(
        Vehicle.society_id == s.sid, Vehicle.is_active == True)  # noqa: E712
        if fid and getattr(vt, "value", vt) in TWO_WHEELERS}
    cycle = (s.db.query(BillingCycle).filter(BillingCycle.society_id == s.sid, BillingCycle.cycle_start <= s.today,
                                             BillingCycle.cycle_start >= s.today - timedelta(days=150))
             .order_by(BillingCycle.cycle_start.desc()).first())
    if cycle is None:
        return out
    bills = (s.db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
             .filter(MaintenanceBill.cycle_id == cycle.id, MaintenanceBill.bill_status.in_(LIVE_BILL)).all())
    held = defaultdict(list)
    for a in allocs:
        if a.flat_id and _overlaps(a.start_date, _held_until(a), cycle.cycle_start, cycle.cycle_end):
            held[a.flat_id].append(a)
    for b in bills:
        billed = sum((_money(li.amount) for li in b.line_items if li.charge_type == ChargeType.PARKING), D0)
        slots_held = [a for a in held.get(b.flat_id, []) if a.monthly_charge != 0]
        if slots_held and not billed:
            nums = [slots[a.slot_id].slot_number for a in slots_held if a.slot_id in slots]
            out.append(LDraft("A-PRK-01", "accounting", "maintenance_billing", "parking", "SUSPECTED_ACCOUNTING_ANOMALY", "MEDIUM", 0.75,
                              f"{s.flat_label(b.flat_id)} holds parking slot(s) {', '.join(nums) or ''} but {b.invoice_number} has no parking charge",
                              f"{s.flat_label(b.flat_id)} held {len(slots_held)} allotted slot(s) during {cycle.name}, but its bill "
                              f"{b.invoice_number} carries no parking line. Parking income is being missed, or the allotment "
                              "should have been released.",
                              expected="A parking line for each chargeable slot held", actual="No parking line",
                              recommended="Check the allotment dates in Parking; add the charge by a debit note if it was due.",
                              evidence={"cycle": cycle.name, "slots": nums, "bill": b.invoice_number},
                              subject=f"{cycle.id}:{b.flat_id}", flat_id=b.flat_id, transaction_ref=b.invoice_number,
                              voucher_date=b.bill_date))
        elif billed and not held.get(b.flat_id) and not (two_wheeler_rate and b.flat_id in tw_flats):
            out.append(LDraft("A-PRK-02", "accounting", "maintenance_billing", "parking", "SUSPECTED_ACCOUNTING_ANOMALY", "MEDIUM", 0.75,
                              f"{s.flat_label(b.flat_id)} was billed {_inr(billed)} for parking with no slot allotted",
                              f"Bill {b.invoice_number} ({cycle.name}) charges {_inr(billed)} for parking, but {s.flat_label(b.flat_id)} "
                              "held no allotted slot during that period.",
                              expected="No parking charge without an allotment", actual=_inr(billed),
                              recommended="Record the allotment in Parking if one exists; otherwise issue a credit note.",
                              evidence={"cycle": cycle.name, "billed": str(billed), "bill": b.invoice_number},
                              subject=f"{cycle.id}:{b.flat_id}", flat_id=b.flat_id, transaction_ref=b.invoice_number,
                              voucher_date=b.bill_date))
    return out


# ── Unadjusted advances ────────────────────────────────────────────────────────────────────────────────────────────

def chk_unadjusted_advances(s) -> List:
    from app.modules.accounts_agent.legal.compliance import LDraft
    from app.modules.billing.models.billing import MaintenanceBill, OnlinePaymentSubmission, ReconciliationStatus
    from app.modules.billing.services.allocations import OPEN_STATUSES, PaymentAllocator, unapplied
    out = []
    advances = PaymentAllocator(s.db).society_unapplied(s.sid)
    for fid, adv in advances.items():
        adv = _money(adv)
        if adv < Decimal("1"):
            continue
        open_bills = (s.db.query(MaintenanceBill).filter(MaintenanceBill.society_id == s.sid, MaintenanceBill.flat_id == fid,
                                                         MaintenanceBill.bill_status.in_(OPEN_STATUSES),
                                                         MaintenanceBill.outstanding > 0).all())
        due = sum((_money(b.outstanding) for b in open_bills), D0)
        flat = s.flat_label(fid)
        if due > 0:
            out.append(LDraft("A-ADV-01", "accounting", "member_ledger", "advances", "SUSPECTED_ACCOUNTING_ANOMALY", "MEDIUM", 0.85,
                              f"{flat}: advance of {_inr(adv)} not set off against {_inr(due)} of unpaid bills",
                              f"{flat} has {_inr(adv)} of payments not yet set off, while {len(open_bills)} issued bill(s) show "
                              f"{_inr(due)} outstanding. The member appears in arrears (and may be charged interest) although "
                              "the society holds their money.",
                              expected="Advance set off against the oldest open bill", actual="Advance and dues both open",
                              recommended="Apply the member's credit to the open bills from Billing (set-off), then re-check interest.",
                              evidence={"advance": str(adv), "outstanding": str(due), "can_set_off": str(min(adv, due)),
                                        "bills": [b.invoice_number for b in open_bills[:10]],
                                        "calculation": f"min({adv}, {due}) = {min(adv, due)}"},
                              subject=str(fid), flat_id=fid))
            continue
        subs = (s.db.query(OnlinePaymentSubmission).filter(OnlinePaymentSubmission.society_id == s.sid,
                                                           OnlinePaymentSubmission.flat_id == fid,
                                                           OnlinePaymentSubmission.is_active == True,  # noqa: E712
                                                           OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED)
                .order_by(OnlinePaymentSubmission.payment_date).all())
        oldest = next((x.payment_date for x in subs if unapplied(x) > 0), None)
        if oldest and (s.today - oldest).days > OLD_ADVANCE_DAYS:
            out.append(LDraft("A-ADV-02", "accounting", "member_ledger", "advances", "ADVISORY_OBSERVATION", "LOW", 0.5,
                              f"{flat}: advance of {_inr(adv)} unused for {(s.today - oldest).days} days",
                              f"{flat} has held {_inr(adv)} of unadjusted payments since {oldest}. A long-standing credit "
                              "usually means a payment that was never matched to its bill, an overpayment due for refund, or "
                              "a previous owner's money.",
                              recommended="Match the payment to its bill, or refund it with the committee's approval.",
                              evidence={"advance": str(adv), "oldest_payment": oldest.isoformat()},
                              subject=str(fid), flat_id=fid))
    return out


CHECKS = [chk_vendor_bank_changes, chk_ownership_handover, chk_parking, chk_unadjusted_advances]
