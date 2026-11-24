"""Draft notices and agendas: AGM, SGM, Managing Committee meeting, and dues reminders.

Drafts only. The text is built from the society's own records (pending approvals, open findings, dues, compliance
items) and quotes the bye-law clauses found in the Legal Library for notice periods, quorum and interest. No figure
that should come from the bye-laws (notice period, quorum, interest rate) is written in unless a clause or a rule in
the registry provides it; otherwise the draft says it must be checked. Saving creates DRAFT notices only; the
committee edits and publishes them through Notices as usual.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.society import Society
from app.modules.accounts_agent.assist import bylaws
from app.modules.accounts_agent.services import audit
from app.utils.local_time import society_today

KINDS = ("AGM", "SGM", "COMMITTEE", "DUES")


def _inr(v) -> str:
    return f"₹{Decimal(str(v or 0)):,.2f}"


def _clauses(db, sid, query: str, must: tuple = (), k: int = 2) -> List[dict]:
    """The best-matching clauses that also contain every word in `must` (so a committee-meeting notice never cites
    the general-meeting clause just because both mention 'notice' and 'meeting')."""
    hits = [c for c in bylaws.search(db, sid, query, k=8)
            if all(w in f"{c['heading'] or ''} {c['text']}".lower() for w in must)]
    return [{"clause_ref": c["clause_ref"], "heading": c["heading"], "page": c["page"], "source": c["source"],
             "document_title": c["document_title"], "society_specific": c["society_specific"],
             "text": c["text"][:600]} for c in hits[:k]]


def _ref_line(refs: List[dict], what: str) -> str:
    if not refs:
        return (f"{what}: no bye-law clause on this is in the Legal Library — check your registered bye-laws "
                "before issuing this notice.")
    r = refs[0]
    return (f"{what}: see {r['source']} clause {r['clause_ref']}" + (f" (page {r['page']})" if r["page"] else "")
            + ("" if r["society_specific"] else " — model bye-laws; confirm against your registered bye-laws") + ".")


def _fy_label(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y - 1}-{str(y)[-2:]}"


def _meeting_header(society: Society, kind: str, when: dict) -> List[str]:
    title = {"AGM": "NOTICE OF THE ANNUAL GENERAL MEETING", "SGM": "NOTICE OF A SPECIAL GENERAL MEETING",
             "COMMITTEE": "MANAGING COMMITTEE MEETING — AGENDA"}[kind]
    lines = [society.name, title, ""]
    at = []
    if when.get("meeting_date"):
        at.append(f"Date: {when['meeting_date']:%d %B %Y}")
    if when.get("time"):
        at.append(f"Time: {when['time']}")
    if when.get("venue"):
        at.append(f"Venue: {when['venue']}")
    lines += at or ["Date, time and venue: to be filled in."]
    return lines + [""]


def _agm(db, sid, society, p, today) -> dict:
    fy = p.get("financial_year") or _fy_label(today)
    from app.modules.accounts_agent.legal.models import LegalDocument
    audit_on_record = db.query(LegalDocument.id).filter(LegalDocument.society_id == sid,
                                                        LegalDocument.document_type == "AUDIT_REPORT").first()
    items = [
        "To read and confirm the minutes of the previous General Meeting.",
        f"To receive and adopt the audited accounts (balance sheet and income & expenditure account) for {fy}.",
        f"To consider the statutory audit report for {fy} and the audit rectification report."
        + ("" if audit_on_record else " (No audit report is uploaded in the Legal Library yet.)"),
        "To appoint the statutory auditor for the next financial year and fix the remuneration.",
        "To approve the budget for the next financial year.",
        *[i for i in (p.get("extra_items") or []) if i],
        "Any other item with the permission of the Chair.",
    ]
    refs = {"notice": _clauses(db, sid, "notice of general meeting days annual general meeting", ("notice", "general")),
            "quorum": _clauses(db, sid, "quorum general meeting", ("quorum", "general"))}
    return {"title": f"Annual General Meeting {fy}", "items": items, "refs": refs, "category": "general"}


def _sgm(db, sid, society, p, today) -> dict:
    subject = (p.get("subject") or "").strip()
    if not subject:
        raise HTTPException(422, "Give the subject of the Special General Meeting.")
    resolutions = [r for r in (p.get("resolutions") or []) if r]
    items = [f"To consider and decide on: {subject}."]
    items += [f"Resolution {i}: {r}" for i, r in enumerate(resolutions, 1)]
    items.append("Any other item connected with the above, with the permission of the Chair.")
    refs = {"notice": _clauses(db, sid, "notice special general meeting days requisition", ("notice", "general")),
            "quorum": _clauses(db, sid, "quorum special general meeting", ("quorum", "general"))}
    return {"title": f"Special General Meeting — {subject[:80]}", "items": items, "refs": refs, "category": "general"}


def _committee(db, sid, society, p, today) -> dict:
    from app.modules.accounts.models.accounts import Voucher
    from app.modules.accounts_agent.legal import recovery
    from app.modules.accounts_agent.legal.models import ComplianceItem
    from app.modules.accounts_agent.models.agent import OPEN_FINDING_STATUSES, AgentFinding, AgentProposal
    items = ["To confirm the minutes of the previous committee meeting."]
    n, amt = (db.query(func.count(Voucher.id), func.coalesce(func.sum(Voucher.amount), 0))
              .filter(Voucher.society_id == sid, Voucher.approval_status == "pending",
                      Voucher.is_cancelled == False).one())  # noqa: E712
    if n:
        items.append(f"To approve or reject {n} pending voucher(s) totalling {_inr(amt)}.")
    props = db.query(func.count(AgentProposal.id)).filter(AgentProposal.society_id == sid,
                                                          AgentProposal.status == "PENDING").scalar() or 0
    if props:
        items.append(f"To decide {props} correction proposal(s) from the Accounts Agent.")
    high = (db.query(AgentFinding).filter(AgentFinding.society_id == sid,
                                          AgentFinding.status.in_(OPEN_FINDING_STATUSES),
                                          AgentFinding.severity.in_(("CRITICAL", "HIGH")))
            .order_by(AgentFinding.created_at.desc()).limit(5).all())
    if high:
        items.append("To review the Accounts Agent's high-priority findings: "
                     + "; ".join(f.title for f in high) + ".")
    rep = recovery.arrears(db, sid, today)
    if rep["flats"]:
        dflt = [r for r in rep["flats"] if r["defaulter"]]
        items.append(f"To review member dues: {_inr(rep['total_outstanding'])} outstanding from {len(rep['flats'])} "
                     f"flat(s)" + (f", {len(dflt)} beyond the defaulter period; decide on reminders or recovery." if dflt
                                   else "."))
    overdue = (db.query(ComplianceItem).filter(ComplianceItem.society_id == sid,
                                               ComplianceItem.completion_status == "PENDING",
                                               ComplianceItem.applicability == "APPLICABLE",
                                               ComplianceItem.due_date.isnot(None), ComplianceItem.due_date < today)
               .all())
    if overdue:
        items.append("Overdue statutory items: " + "; ".join(f"{c.title} (due {c.due_date:%d %b %Y})" for c in overdue)
                     + ".")
    items += [i for i in (p.get("extra_items") or []) if i]
    items.append("Any other item with the permission of the Chairman.")
    refs = {"notice": _clauses(db, sid, "managing committee meeting notice", ("notice", "committee")),
            "quorum": _clauses(db, sid, "quorum managing committee meeting", ("quorum", "committee"))}
    return {"title": "Managing Committee meeting", "items": items, "refs": refs, "category": "general"}


def _meeting_draft(db, sid, society, kind, p, today) -> dict:
    body = {"AGM": _agm, "SGM": _sgm, "COMMITTEE": _committee}[kind](db, sid, society, p, today)
    lines = _meeting_header(society, kind, p)
    if kind != "COMMITTEE":
        lines.append("Notice is hereby given that the meeting of the members of the society will be held as above "
                     "to transact the following business:")
    lines += ["", "AGENDA"] + [f"{i}. {t}" for i, t in enumerate(body["items"], 1)] + [""]
    lines.append(_ref_line(body["refs"]["notice"], "Notice period"))
    lines.append(_ref_line(body["refs"]["quorum"], "Quorum"))
    lines += ["", "By order of the Managing Committee", "Hon. Secretary", society.name]
    return {"kind": kind, "title": body["title"], "content": "\n".join(lines), "agenda_items": body["items"],
            "bylaw_refs": body["refs"]["notice"] + body["refs"]["quorum"], "category": body["category"],
            "audience": "committee" if kind == "COMMITTEE" else "owners_only", "drafts": None}


def _dues(db, sid, society, p, today) -> dict:
    from app.modules.accounts_agent.legal import recovery, registry
    rep = recovery.arrears(db, sid, today)
    only_defaulters = p.get("only_defaulters", True)
    rows = [r for r in rep["flats"] if (r["defaulter"] or not only_defaulters)]
    if not rows:
        raise HTTPException(422, "No flat has dues matching this choice.")
    pay_within = int(p.get("pay_within_days") or 15)
    interest_refs = _clauses(db, sid, "interest arrears dues defaulter payment", ("interest",))
    app = registry.resolve(db, sid, "charges.interest_on_arrears.max_rate_pct", today)
    rate_line = ""
    if app.rule is not None and app.effective_value is not None:
        rate_line = (f"Interest on arrears may be charged as permitted ({app.rule.rule_code}, "
                     f"{'verified' if app.rule.verification_status.startswith('VERIFIED') else 'pending verification'}).")
    drafts = []
    for r in rows:
        lines = [society.name, "REMINDER — MAINTENANCE DUES", "", f"Date: {today:%d %B %Y}", f"To: The member, Flat {r['flat']}",
                 "", f"Our records show {_inr(r['outstanding'])} outstanding on {r['bills']} bill(s)"
                 + (f", the oldest due on {date.fromisoformat(r['oldest_due']):%d %B %Y}" if r["oldest_due"] else "")
                 + ".", f"Please pay within {pay_within} days of this notice. If you have already paid, please "
                 "share the payment details with the office so that the account can be updated."]
        if rate_line:
            lines.append(rate_line)
        lines.append(_ref_line(interest_refs, "Bye-law on interest and dues"))
        lines += ["", "Hon. Secretary / Treasurer", society.name]
        drafts.append({"flat_id": r["flat_id"], "flat": r["flat"], "outstanding": r["outstanding"],
                       "title": f"Dues reminder — {r['flat']}", "content": "\n".join(lines)})
    return {"kind": "DUES", "title": f"Dues reminders ({len(drafts)} flat(s))", "content": None, "agenda_items": None,
            "bylaw_refs": interest_refs, "category": "finance", "audience": "specific_flats", "drafts": drafts}


def draft(db: Session, society_id: UUID, user, kind: str, params: dict, save: bool) -> dict:
    kind = (kind or "").upper()
    if kind not in KINDS:
        raise HTTPException(422, f"Kind must be one of {', '.join(KINDS)}")
    society = db.get(Society, society_id)
    today = society_today(db, society_id)
    out = _dues(db, society_id, society, params, today) if kind == "DUES" else \
        _meeting_draft(db, society_id, society, kind, params, today)
    out["saved_notice_ids"] = []
    if save:
        out["saved_notice_ids"] = _save(db, society_id, user, out)
    audit.record(db, society_id, "notice_drafted", "society", society_id, user.id,
                 {"kind": kind, "saved": len(out["saved_notice_ids"])})
    db.commit()
    return out


def _save(db: Session, society_id: UUID, user, d: dict) -> List[str]:
    """DRAFT notices only — never published here."""
    from app.modules.notice.models.notice import AudienceType, Notice, NoticeCategory, NoticeStatus
    cat = NoticeCategory.FINANCE if d["category"] == "finance" else NoticeCategory.GENERAL
    ids = []
    if d["kind"] == "DUES":
        for x in d["drafts"]:
            n = Notice(society_id=society_id, created_by=user.id, title=x["title"][:255], content=x["content"],
                       category=cat, status=NoticeStatus.DRAFT, audience_type=AudienceType.SPECIFIC_FLATS,
                       target_flat_ids=[x["flat_id"]])
            db.add(n)
            db.flush()
            ids.append(str(n.id))
    else:
        aud = AudienceType.COMMITTEE if d["audience"] == "committee" else AudienceType.OWNERS_ONLY
        n = Notice(society_id=society_id, created_by=user.id, title=d["title"][:255], content=d["content"],
                   category=cat, status=NoticeStatus.DRAFT, audience_type=aud)
        db.add(n)
        db.flush()
        ids.append(str(n.id))
    return ids
