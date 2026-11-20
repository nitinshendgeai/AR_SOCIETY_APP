"""Member arrears and recovery readiness (Section 154B-29 / Rule 106C-14).

This module only REPORTS. It never issues a notice, files an application, contacts a member or changes a bill: any
legal action needs an explicit decision of the Managing Committee and, where appropriate, professional advice. The
readiness checklist says which supporting records are present in the app and which must be gathered by hand.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.models.wing import Wing
from app.modules.accounts_agent.legal import registry, resolutions
from app.modules.accounts_agent.legal.models import OPERATIVE_DOCUMENT_STATUSES, VERIFIED, LegalDocument, SocietyResolution
from app.modules.billing.models.billing import BillStatus, MaintenanceBill, MaintenanceSettings

OPEN = (BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE, BillStatus.GENERATED)
BUCKETS = ((30, "0-30"), (90, "31-90"), (180, "91-180"), (365, "181-365"), (None, "365+"))
NO_ACTION = ("The Accounts Agent does not issue notices, file recovery applications or start any legal action. "
             "This is a readiness review for the Managing Committee and its advisor.")


def money(v) -> Decimal:
    return Decimal(str(v if v is not None else 0)).quantize(Decimal("0.01"))


def _bucket(days: int) -> str:
    for limit, name in BUCKETS:
        if limit is None or days <= limit:
            return name
    return "365+"


def arrears(db: Session, society_id: UUID, today: date) -> dict:
    app = registry.resolve(db, society_id, "recovery.certificate", today)
    months = int((app.rule.calculation_method or {}).get("defaulter_after_months", 3)) if app.rule else 3
    flats = {f.id: f"{w.name}-{f.flat_number}" for f, w in
             db.query(Flat, Wing).join(Wing, Wing.id == Flat.wing_id).filter(Wing.society_id == society_id)}
    rows = defaultdict(lambda: {"outstanding": Decimal("0"), "oldest_due": None, "bills": 0,
                                "ageing": defaultdict(lambda: Decimal("0"))})
    for b in db.query(MaintenanceBill).filter(MaintenanceBill.society_id == society_id, MaintenanceBill.bill_status.in_(OPEN),
                                              MaintenanceBill.outstanding > 0):
        if b.flat_id not in flats:
            continue
        r = rows[b.flat_id]
        amt = money(b.outstanding)
        r["outstanding"] += amt
        r["bills"] += 1
        if b.due_date < today:
            r["ageing"][_bucket((today - b.due_date).days)] += amt
            r["oldest_due"] = min(r["oldest_due"] or b.due_date, b.due_date)
    out = []
    for fid, r in rows.items():
        overdue_days = (today - r["oldest_due"]).days if r["oldest_due"] else 0
        out.append({"flat_id": str(fid), "flat": flats[fid], "outstanding": str(r["outstanding"]), "bills": r["bills"],
                    "oldest_due": r["oldest_due"].isoformat() if r["oldest_due"] else None, "overdue_days": overdue_days,
                    "ageing": {k: str(v) for k, v in r["ageing"].items()},
                    "defaulter": overdue_days > months * 30})
    out.sort(key=lambda x: (-x["overdue_days"], x["flat"]))
    totals = defaultdict(lambda: Decimal("0"))
    for r in out:
        for k, v in r["ageing"].items():
            totals[k] += Decimal(v)
    return {"as_of": today.isoformat(), "defaulter_after_months": months, "flats": out,
            "total_outstanding": str(sum((Decimal(r["outstanding"]) for r in out), Decimal("0"))),
            "ageing_totals": {name: str(totals.get(name, Decimal("0"))) for _, name in BUCKETS},
            "rule": registry.source_ref(app.rule, app), "note": NO_ACTION}


def checklist(db: Session, society_id: UUID, flat_id: UUID, today: date) -> dict:
    flat = (db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
            .filter(Flat.id == flat_id, Wing.society_id == society_id).first())
    if flat is None:
        raise HTTPException(404, "Flat not found")
    rep = arrears(db, society_id, today)
    row = next((r for r in rep["flats"] if r["flat_id"] == str(flat_id)), None)
    app = registry.resolve(db, society_id, "recovery.certificate", today)
    cap = registry.resolve(db, society_id, "charges.interest_on_arrears.max_rate_pct", today)
    ms = db.query(MaintenanceSettings).filter(MaintenanceSettings.society_id == society_id).first()
    bylaw_ok = db.query(LegalDocument.id).filter(LegalDocument.society_id == society_id,
                                                 LegalDocument.document_type == "REGISTERED_BYELAWS",
                                                 LegalDocument.status.in_(OPERATIVE_DOCUMENT_STATUSES),
                                                 LegalDocument.verification_status.in_(VERIFIED)).first() is not None
    res = (db.query(SocietyResolution).filter(SocietyResolution.society_id == society_id,
                                              SocietyResolution.category == "recovery",
                                              SocietyResolution.approval_authority == "MANAGING_COMMITTEE",
                                              SocietyResolution.status.in_(resolutions.LIVE)).all())
    res_ok = any(not resolutions.problems(r) for r in res)
    rate = money(ms.interest_rate_pct) if ms else None
    rate_ok = None if (rate is None or cap.effective_value is None) else rate <= Decimal(str(cap.effective_value))

    def item(label, status, detail):
        return {"item": label, "status": status, "detail": detail}

    items = [
        item("Dues are overdue beyond the defaulter period", "OK" if row and row["defaulter"] else "NOT_MET",
             f"Oldest unpaid due: {row['oldest_due']} ({row['overdue_days']} days)" if row else "No unpaid bills"),
        item("Bills raised for the period claimed", "OK" if row and row["bills"] else "NOT_MET",
             f"{row['bills']} unpaid bill(s) on record" if row else "None"),
        item("Member statement reconciled with bills and receipts", "MANUAL",
             "Open the member's statement in Accounts and confirm it agrees with the bills."),
        item("Demand / reminder notice served, with proof of service", "MANUAL",
             "Notices and proof of service are not recorded in the app; attach copies."),
        item("Interest charged at the rate allowed", {True: "OK", False: "NOT_MET", None: "MANUAL"}[rate_ok],
             f"Configured {rate}% p.a.; ceiling on record {cap.effective_value}% p.a. (verification: "
             f"{cap.rule.verification_status if cap.rule else 'n/a'})"),
        item("Managing Committee resolution authorising the recovery application", "OK" if res_ok else "MISSING",
             "Found in the resolution register" if res_ok else "Not in the resolution register"),
        item("Registered bye-laws on record (clauses relied on)", "OK" if bylaw_ok else "MISSING",
             "Verified registered bye-laws are in the Legal Library" if bylaw_ok else "Upload and verify them"),
    ]
    ready = all(i["status"] in ("OK", "MANUAL") for i in items)
    return {"flat_id": str(flat_id), "flat": row["flat"] if row else str(flat.flat_number), "arrears": row,
            "readiness": "READY_FOR_PROFESSIONAL_REVIEW" if ready else "INCOMPLETE",
            "checklist": items, "required_evidence": (app.rule.required_evidence if app.rule else []),
            "rule": registry.source_ref(app.rule, app), "note": NO_ACTION}
