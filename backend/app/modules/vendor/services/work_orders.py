"""Giving work to vendors the way the model bye-laws require.

Bye-law 157 (Maharashtra model bye-laws for co-operative housing societies):
- The committee may spend on repairs and maintenance of the society's
  property on its own only up to a limit — ₹25,000 for a society of up to 25
  members, ₹50,000 up to 50 and ₹1,00,000 above (or what the general body
  fixes). Beyond it the general body's prior sanction is needed.
- The general body fixes the amount up to which the committee may get work
  done without calling for tenders. Above it, tenders are invited, the
  Secretary opens them in a committee meeting, the committee scrutinises them
  and places them with its report before the general body, which decides.
- A committee member may not have an interest in a contract with the society
  (it disqualifies them), so the sanction carries the committee's declaration
  and the vendor is checked against the committee members' phone and email.

A work order therefore goes: draft (quotations collected) → sanctioned
(committee resolution, and the general body's where needed) → issued (the
written order) → completed (certified by the committee) → closed (every bill
paid). Bills against it can't exceed the sanctioned amount; before completion
only the agreed advance can be paid, and the retention is held until the
defect liability period ends. Annual contracts take the same sanction.
"""
import calendar
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.user import User
from app.modules.vendor.models.vendor import (
    AMCContract, ContractStatus, ProcurementSettings, Quotation, SanctionLevel, Vendor,
    VendorInvoice, VendorStatus, WorkOrder, WorkOrderStatus,
)
from app.services.audit_service import AuditService

ZERO = Decimal("0")
COMMITTEE_ROLES = ("Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member")
STATUS_LABEL = {
    WorkOrderStatus.DRAFT: "Collecting quotations",
    WorkOrderStatus.SANCTIONED: "Sanctioned",
    WorkOrderStatus.ISSUED: "Work order issued",
    WorkOrderStatus.COMPLETED: "Completed",
    WorkOrderStatus.CLOSED: "Closed",
    WorkOrderStatus.CANCELLED: "Cancelled",
}


def money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def inr(v) -> str:
    v = money(v)
    whole, paise = f"{v:.2f}".split(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"₹{sign}{','.join(groups + [tail]) if groups else tail}" + ("" if paise == "00" else f".{paise}")


def add_months(d: date, months: int) -> date:
    """The same day `months` later, or the month's last day when it is shorter
    (31 January + 1 month = 28/29 February)."""
    index = d.year * 12 + d.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(d.day, calendar.monthrange(year, month + 1)[1]))


def bye_law_slab(members: int) -> Decimal:
    """The committee's limit under bye-law 157 for a society of this size."""
    if members <= 25:
        return Decimal("25000")
    if members <= 50:
        return Decimal("50000")
    return Decimal("100000")


def member_count(db: Session, society_id: UUID) -> int:
    from app.models.flat import Flat
    return db.query(func.count(Flat.id)).filter(
        Flat.wing.has(society_id=society_id), Flat.is_active == True).scalar() or 0  # noqa: E712


def procurement_limits(db: Session, society_id: UUID) -> dict:
    s = db.query(ProcurementSettings).filter(ProcurementSettings.society_id == society_id).first()
    members = member_count(db, society_id)
    slab = bye_law_slab(members)
    committee = money(s.committee_limit) if s and s.committee_limit is not None else slab
    tender = money(s.tender_limit) if s and s.tender_limit is not None else committee
    return {
        "members": members,
        "bye_law_limit": str(slab),
        "committee_limit": str(committee),
        "committee_limit_set": bool(s and s.committee_limit is not None),
        "tender_limit": str(tender),
        "tender_limit_set": bool(s and s.tender_limit is not None),
        "min_quotations": s.min_quotations if s else 3,
        "gb_resolution_no": s.gb_resolution_no if s else None,
        "gb_meeting_date": s.gb_meeting_date.isoformat() if s and s.gb_meeting_date else None,
    }


def requirements(limits: dict, amount: Optional[Decimal]) -> dict:
    """What the bye-laws need before work of this amount can be given."""
    committee, tender = Decimal(limits["committee_limit"]), Decimal(limits["tender_limit"])
    needs_tenders = amount is not None and amount > tender
    needs_gb = amount is not None and (amount > committee or needs_tenders)
    return {
        "amount": str(money(amount)) if amount is not None else None,
        "committee_limit": limits["committee_limit"],
        "tender_limit": limits["tender_limit"],
        "min_quotations": limits["min_quotations"] if needs_tenders else 1,
        "needs_tenders": needs_tenders,
        "needs_general_body": needs_gb,
    }


def committee_interest(db: Session, society_id: UUID, vendor: Vendor) -> Optional[str]:
    """The committee member whose phone or email the vendor's is, if any."""
    from app.models.role import Role
    from app.models.user import UserRole
    members = (db.query(User).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
               .filter(User.society_id == society_id, Role.name.in_(COMMITTEE_ROLES),
                       UserRole.is_active == True, User.is_active == True).all())  # noqa: E712

    def digits(v):
        d = "".join(ch for ch in (v or "") if ch.isdigit())
        return d[-10:] if len(d) >= 10 else None

    v_phone, v_email = digits(vendor.mobile), (vendor.email or "").strip().lower() or None
    for u in members:
        if v_phone and digits(u.phone) == v_phone:
            return f"{u.full_name} (same mobile number)"
        if v_email and (u.email or "").strip().lower() == v_email:
            return f"{u.full_name} (same email)"
    return None


def _not_future(d: Optional[date], what: str):
    if d and d > date.today():
        raise HTTPException(422, f"The {what} can't be in the future")


class Sanction:
    """The checks a decision to award work must pass, shared by work orders
    and annual contracts."""

    def __init__(self, db: Session):
        self.db = db

    def apply(self, record, quotations: List[Quotation], data: dict, user: User) -> Quotation:
        live = [q for q in quotations if q.is_active]
        chosen = next((q for q in live if str(q.id) == str(data["quotation_id"])), None)
        if chosen is None:
            raise HTTPException(422, "Choose one of the quotations received")
        vendor = chosen.vendor
        if vendor.status != VendorStatus.ACTIVE:
            raise HTTPException(422, f"{vendor.company_name} is {vendor.status.value.replace('_', ' ')} "
                                     f"and can't be given work")
        meeting = data["committee_meeting_date"]
        _not_future(meeting, "committee meeting date")
        if chosen.quotation_date > meeting:
            raise HTTPException(422, "The chosen quotation is dated after the committee meeting")
        if chosen.valid_until and chosen.valid_until < meeting:
            raise HTTPException(422, f"{vendor.company_name}'s quotation expired on "
                                     f"{chosen.valid_until:%d-%m-%Y}, before the committee meeting")

        amount = money(chosen.total_amount)
        need = requirements(procurement_limits(self.db, record.society_id), amount)
        if need["needs_tenders"]:
            vendors = {q.vendor_id for q in live}
            if len(vendors) < need["min_quotations"]:
                raise HTTPException(422, f"Work of {inr(amount)} is above the tender limit of "
                                         f"{inr(need['tender_limit'])}: tenders from at least "
                                         f"{need['min_quotations']} vendors are needed (bye-law 157); "
                                         f"{len(vendors)} received")
            opened = data.get("tenders_opened_on")
            if not opened:
                raise HTTPException(422, "Enter the date the tenders were opened in the committee meeting")
            _not_future(opened, "date the tenders were opened")
            late = [q.vendor.company_name for q in live if q.quotation_date > opened]
            if late:
                raise HTTPException(422, f"Tenders dated after they were opened can't be considered: "
                                         f"{', '.join(late)}")
        if need["needs_general_body"]:
            if not data.get("gb_resolution_no") or not data.get("gb_meeting_date"):
                why = ("tenders were invited" if need["needs_tenders"] else
                       f"it is more than the committee's limit of {inr(need['committee_limit'])}")
                raise HTTPException(422, f"Work of {inr(amount)} needs the general body's sanction because {why} "
                                         f"(bye-law 157): enter the general body resolution number and date")
            _not_future(data["gb_meeting_date"], "general body meeting date")
            if need["needs_tenders"] and data["gb_meeting_date"] < data["tenders_opened_on"]:
                raise HTTPException(422, "The general body decides after the tenders are opened and scrutinised")

        lowest = min(live, key=lambda q: q.total_amount)
        reason = (data.get("selection_reason") or "").strip() or None
        if money(chosen.total_amount) > money(lowest.total_amount) and not reason:
            raise HTTPException(422, f"{lowest.vendor.company_name} quoted less ({inr(lowest.total_amount)}); "
                                     f"record why {vendor.company_name} was chosen")
        if not data.get("no_interest_declared"):
            raise HTTPException(422, "The committee must declare that none of its members has an interest "
                                     "in this work (a member with an interest is disqualified)")
        interested = committee_interest(self.db, record.society_id, vendor)
        if interested:
            raise HTTPException(422, f"{vendor.company_name}'s contact matches committee member {interested}. "
                                     f"A committee member can't have an interest in a contract with the society")

        for q in live:
            q.is_selected = q.id == chosen.id
        record.vendor_id = vendor.id
        record.sanctioned_amount = amount
        record.sanction_level = SanctionLevel.GENERAL_BODY if need["needs_general_body"] else SanctionLevel.COMMITTEE
        record.committee_resolution_no = data["committee_resolution_no"]
        record.committee_meeting_date = meeting
        record.gb_resolution_no = data.get("gb_resolution_no") if need["needs_general_body"] else None
        record.gb_meeting_date = data.get("gb_meeting_date") if need["needs_general_body"] else None
        record.tenders_opened_on = data.get("tenders_opened_on") if need["needs_tenders"] else None
        record.selection_reason = reason
        record.no_interest_declared = True
        record.sanctioned_by = user.id
        record.sanctioned_at = datetime.utcnow()
        return chosen


def sanction_out(r) -> dict:
    return {
        "sanctioned_amount": str(r.sanctioned_amount) if r.sanctioned_amount is not None else None,
        "sanction_level": r.sanction_level.value if r.sanction_level else None,
        "committee_resolution_no": r.committee_resolution_no,
        "committee_meeting_date": r.committee_meeting_date.isoformat() if r.committee_meeting_date else None,
        "gb_resolution_no": r.gb_resolution_no,
        "gb_meeting_date": r.gb_meeting_date.isoformat() if r.gb_meeting_date else None,
        "tenders_opened_on": r.tenders_opened_on.isoformat() if r.tenders_opened_on else None,
        "selection_reason": r.selection_reason,
        "no_interest_declared": r.no_interest_declared,
        "sanctioned_by_name": r.sanctioner.full_name if r.sanctioner else None,
        "sanctioned_at": r.sanctioned_at.isoformat() if r.sanctioned_at else None,
    }


def quotation_out(q: Quotation, lowest_id=None) -> dict:
    return {
        "id": str(q.id),
        "vendor_id": str(q.vendor_id),
        "vendor_name": q.vendor.company_name if q.vendor else None,
        "vendor_code": q.vendor.vendor_code if q.vendor else None,
        "quotation_ref": q.quotation_ref,
        "quotation_date": q.quotation_date.isoformat(),
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "amount": str(q.amount),
        "gst_amount": str(q.gst_amount),
        "total_amount": str(q.total_amount),
        "remarks": q.remarks,
        "doc_url": q.doc_url,
        "is_selected": q.is_selected,
        "is_lowest": lowest_id is not None and q.id == lowest_id,
    }


def quotations_out(quotations: List[Quotation]) -> List[dict]:
    live = [q for q in quotations if q.is_active]
    lowest = min(live, key=lambda q: q.total_amount).id if live else None
    return [quotation_out(q, lowest) for q in live]


class WorkOrderService:

    def __init__(self, db: Session):
        self.db = db

    # ── helpers ───────────────────────────────────────────────────────────────

    def _audit(self, action, wo, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="vendor", entity_id=str(wo.id),
                         entity_type="WorkOrder", user=user, request=request, **kw)

    def get(self, wo_id: UUID, user: Optional[User] = None) -> WorkOrder:
        wo = self.db.get(WorkOrder, wo_id)
        if wo is None or not wo.is_active or (user is not None and user.society_id is not None
                                              and wo.society_id != user.society_id):
            raise HTTPException(404, "Work order not found")
        return wo

    def _status(self, wo: WorkOrder, *allowed: WorkOrderStatus, doing: str):
        if wo.status not in allowed:
            raise HTTPException(409, f"Work order {wo.wo_number} is {STATUS_LABEL[wo.status].lower()}; "
                                     f"it can't be {doing}")

    def _next_number(self, society_id: UUID) -> str:
        highest = 0
        for (number,) in self.db.query(WorkOrder.wo_number).filter(WorkOrder.society_id == society_id):
            digits = number.rsplit("-", 1)[-1]
            if digits.isdigit():
                highest = max(highest, int(digits))
        return f"WO-{date.today().year}-{highest + 1:04d}"

    def _links(self, society_id: UUID, data: dict):
        from app.modules.vendor.models.vendor import ServiceRequest
        checks = [("service_request_id", ServiceRequest, "Service request")]
        from app.modules.complaint.models.complaint import Complaint
        from app.modules.inventory.models.inventory import Asset
        from app.modules.accounts.models.accounts import Account
        checks += [("complaint_id", Complaint, "Complaint"), ("asset_id", Asset, "Asset"),
                   ("expense_account_id", Account, "Expense head")]
        for key, model, label in checks:
            if data.get(key):
                obj = self.db.get(model, data[key])
                if obj is None or obj.society_id != society_id or not getattr(obj, "is_active", True):
                    raise HTTPException(422, f"{label} not found in this society")

    @staticmethod
    def _terms(wo: WorkOrder):
        if wo.start_date and wo.due_date and wo.due_date < wo.start_date:
            raise HTTPException(422, "The work must be due on or after its start date")

    def bills(self, wo: WorkOrder) -> List[VendorInvoice]:
        return [i for i in wo.invoices if i.is_active]

    def money_position(self, wo: WorkOrder) -> dict:
        bills = self.bills(wo)
        billed = money(sum((i.total_amount for i in bills), ZERO))
        paid = money(sum((i.paid_amount for i in bills), ZERO))
        retention = money(billed * Decimal(wo.retention_pct or 0) / 100)
        held = retention if wo.retention_pct and not wo.retention_released_on else money(ZERO)
        if wo.status == WorkOrderStatus.ISSUED:
            ceiling = min(money(wo.advance_amount), billed)
        elif wo.status in (WorkOrderStatus.COMPLETED, WorkOrderStatus.CLOSED):
            ceiling = billed - held
        else:
            ceiling = ZERO
        return {k: money(v) for k, v in {"billed": billed, "paid": paid, "retention": retention, "retention_held": held,
                "payable_now": max(ZERO, money(ceiling - paid)),
                "unbilled": max(ZERO, money(wo.sanctioned_amount or 0) - billed)}.items()}

    def retention_due_on(self, wo: WorkOrder) -> Optional[date]:
        if not wo.completed_on:
            return None
        return add_months(wo.completed_on, wo.defect_liability_months or 0)

    # ── draft ─────────────────────────────────────────────────────────────────

    def create(self, data: dict, user: User, request=None) -> WorkOrder:
        data["society_id"] = society_id = resolve_create_society_id(user, data["society_id"])
        self._links(society_id, data)
        wo = WorkOrder(**data, wo_number=self._next_number(society_id), created_by=user.id)
        self._terms(wo)
        self.db.add(wo)
        self.db.flush()
        self._audit(AuditAction.CREATE, wo, user, request, new_values={"number": wo.wo_number, "title": wo.title})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def update(self, wo_id: UUID, data: dict, user: User) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.DRAFT, WorkOrderStatus.SANCTIONED, doing="edited")
        locked = {"advance_amount", "retention_pct", "defect_liability_months", "payment_terms", "scope_of_work"}
        if wo.status == WorkOrderStatus.SANCTIONED and locked & {k for k in data}:
            changed = [k for k in locked & set(data) if getattr(wo, k) != data[k]]
            if changed:
                raise HTTPException(409, "The scope and terms were sanctioned; they can't change now")
        self._links(wo.society_id, data)
        for k, v in data.items():
            setattr(wo, k, v)
        self._terms(wo)
        if wo.sanctioned_amount is not None and money(wo.advance_amount) > money(wo.sanctioned_amount):
            raise HTTPException(422, "The advance can't be more than the sanctioned amount")
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def add_quotation(self, wo_id: UUID, data: dict, user: User) -> Quotation:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.DRAFT, doing="given more quotations")
        q = QuotationBook(self.db).add(wo.society_id, data, user, existing=wo.quotations)
        q.work_order_id = wo.id
        self.db.commit()
        self.db.refresh(q)
        return q

    def remove_quotation(self, wo_id: UUID, q_id: UUID, user: User) -> None:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.DRAFT, doing="changed")
        q = next((q for q in wo.quotations if q.id == q_id and q.is_active), None)
        if q is None:
            raise HTTPException(404, "Quotation not found")
        q.is_active = False
        self.db.commit()

    # ── sanction → issue → complete → close ──────────────────────────────────

    def sanction(self, wo_id: UUID, data: dict, user: User, request=None) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.DRAFT, doing="sanctioned again")
        chosen = Sanction(self.db).apply(wo, wo.quotations, data, user)
        if money(wo.advance_amount) > money(chosen.total_amount):
            raise HTTPException(422, "The advance can't be more than the sanctioned amount")
        wo.status = WorkOrderStatus.SANCTIONED
        self._audit(AuditAction.UPDATE, wo, user, request,
                    new_values={"status": "sanctioned", "vendor": chosen.vendor.company_name,
                                "amount": str(wo.sanctioned_amount), "level": wo.sanction_level.value,
                                "committee_resolution": wo.committee_resolution_no,
                                "gb_resolution": wo.gb_resolution_no})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def revise_sanction(self, wo_id: UUID, data: dict, user: User, request=None) -> WorkOrder:
        """A higher (or lower) amount for work already sanctioned, by a fresh
        resolution; the general body's when the new amount needs it."""
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.SANCTIONED, WorkOrderStatus.ISSUED, WorkOrderStatus.COMPLETED,
                     doing="revised")
        amount = money(data["amount"])
        pos = self.money_position(wo)
        if amount < pos["billed"]:
            raise HTTPException(422, f"Bills of {inr(pos['billed'])} are already recorded against it")
        if amount < money(wo.advance_amount):
            raise HTTPException(422, "The sanctioned amount can't be less than the advance agreed")
        meeting = data["committee_meeting_date"]
        _not_future(meeting, "committee meeting date")
        need = requirements(procurement_limits(self.db, wo.society_id), amount)
        needs_gb = amount > Decimal(need["committee_limit"]) or need["needs_tenders"]
        if needs_gb and (not data.get("gb_resolution_no") or not data.get("gb_meeting_date")):
            raise HTTPException(422, f"{inr(amount)} needs the general body's sanction (bye-law 157): "
                                     f"enter the general body resolution number and date")
        if data.get("gb_meeting_date"):
            _not_future(data["gb_meeting_date"], "general body meeting date")
        old = str(wo.sanctioned_amount)
        wo.sanctioned_amount = amount
        wo.committee_resolution_no = data["committee_resolution_no"]
        wo.committee_meeting_date = meeting
        if needs_gb:
            wo.sanction_level = SanctionLevel.GENERAL_BODY
            wo.gb_resolution_no = data["gb_resolution_no"]
            wo.gb_meeting_date = data["gb_meeting_date"]
        wo.sanctioned_by = user.id
        wo.sanctioned_at = datetime.utcnow()
        self._audit(AuditAction.UPDATE, wo, user, request, old_values={"amount": old},
                    new_values={"amount": str(amount), "reason": data["reason"],
                                "committee_resolution": wo.committee_resolution_no,
                                "gb_resolution": wo.gb_resolution_no})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def issue(self, wo_id: UUID, issued_on: date, user: User, request=None) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.SANCTIONED, doing="issued")
        _not_future(issued_on, "issue date")
        decided = max(d for d in (wo.committee_meeting_date, wo.gb_meeting_date) if d)
        if issued_on < decided:
            raise HTTPException(422, f"The work order can't be issued before it was sanctioned on {decided:%d-%m-%Y}")
        if wo.vendor is None or wo.vendor.status != VendorStatus.ACTIVE:
            raise HTTPException(422, "The vendor is no longer active; the work can't be given to them")
        wo.status = WorkOrderStatus.ISSUED
        wo.issued_on = issued_on
        self._audit(AuditAction.UPDATE, wo, user, request, new_values={"status": "issued", "on": str(issued_on)})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def complete(self, wo_id: UUID, data: dict, user: User, request=None) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.ISSUED, doing="certified complete")
        done = data["completed_on"]
        _not_future(done, "completion date")
        if done < wo.issued_on:
            raise HTTPException(422, "The work can't be completed before the work order was issued")
        wo.status = WorkOrderStatus.COMPLETED
        wo.completed_on = done
        wo.completion_notes = data["completion_notes"]
        wo.certificate_ref = data.get("certificate_ref")
        wo.completed_by = user.id
        self._audit(AuditAction.UPDATE, wo, user, request, new_values={"status": "completed", "on": str(done)})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def release_retention(self, wo_id: UUID, released_on: date, user: User, request=None) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.COMPLETED, doing="have its retention released")
        if not wo.retention_pct:
            raise HTTPException(409, "No retention is held on this work order")
        if wo.retention_released_on:
            raise HTTPException(409, "The retention was already released")
        _not_future(released_on, "release date")
        due = self.retention_due_on(wo)
        if released_on < due:
            raise HTTPException(422, f"The defect liability period runs until {due:%d-%m-%Y}")
        wo.retention_released_on = released_on
        self._audit(AuditAction.UPDATE, wo, user, request, new_values={"retention_released_on": str(released_on)})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def close(self, wo_id: UUID, user: User, request=None) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.COMPLETED, doing="closed")
        unpaid = [i.invoice_number for i in self.bills(wo) if not i.is_paid]
        if unpaid:
            raise HTTPException(409, f"Bills not yet paid in full: {', '.join(unpaid)}")
        wo.status = WorkOrderStatus.CLOSED
        wo.closed_on = date.today()
        self._audit(AuditAction.UPDATE, wo, user, request, new_values={"status": "closed"})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def cancel(self, wo_id: UUID, reason: str, user: User, request=None) -> WorkOrder:
        wo = self.get(wo_id, user)
        self._status(wo, WorkOrderStatus.DRAFT, WorkOrderStatus.SANCTIONED, WorkOrderStatus.ISSUED,
                     doing="cancelled")
        if self.bills(wo):
            raise HTTPException(409, "Bills are recorded against this work order; it can't be cancelled")
        wo.status = WorkOrderStatus.CANCELLED
        wo.cancel_reason = reason
        wo.cancelled_at = datetime.utcnow()
        wo.cancelled_by = user.id
        self._audit(AuditAction.UPDATE, wo, user, request, new_values={"status": "cancelled", "reason": reason})
        self.db.commit()
        self.db.refresh(wo)
        return wo

    def list(self, society_id: UUID, status: Optional[WorkOrderStatus] = None,
             vendor_id: Optional[UUID] = None) -> List[WorkOrder]:
        q = self.db.query(WorkOrder).filter(WorkOrder.society_id == society_id, WorkOrder.is_active == True)  # noqa: E712
        if status:
            q = q.filter(WorkOrder.status == status)
        if vendor_id:
            q = q.filter(WorkOrder.vendor_id == vendor_id)
        return q.order_by(WorkOrder.created_at.desc()).all()

    # ── bills and payments against a work order ──────────────────────────────

    def check_bill(self, wo_id: UUID, data: dict) -> WorkOrder:
        """A vendor's bill may be recorded against an issued or completed work
        order of that vendor, within the sanctioned amount."""
        wo = self.db.get(WorkOrder, wo_id)
        if wo is None or wo.society_id != data["society_id"] or not wo.is_active:
            raise HTTPException(422, "Work order not found in this society")
        if wo.status not in (WorkOrderStatus.ISSUED, WorkOrderStatus.COMPLETED):
            raise HTTPException(422, f"Work order {wo.wo_number} is {STATUS_LABEL[wo.status].lower()}; "
                                     f"bills can be recorded once it is issued")
        if str(wo.vendor_id) != str(data["vendor_id"]):
            raise HTTPException(422, f"Work order {wo.wo_number} was given to {wo.vendor.company_name}")
        pos = self.money_position(wo)
        total = money(data["total_amount"])
        if pos["billed"] + total > money(wo.sanctioned_amount):
            raise HTTPException(422, f"Bills on {wo.wo_number} would come to {inr(pos['billed'] + total)}, more "
                                     f"than the {inr(wo.sanctioned_amount)} sanctioned. Record a revised "
                                     f"sanction first")
        if not data.get("expense_account_id") and wo.expense_account_id:
            data["expense_account_id"] = wo.expense_account_id
        return wo

    def check_payment(self, inv: VendorInvoice, amount: Decimal) -> None:
        wo = inv.work_order
        if wo is None:
            return
        pos = self.money_position(wo)
        if money(amount) <= pos["payable_now"]:
            return
        if wo.status == WorkOrderStatus.ISSUED:
            raise HTTPException(422, f"Until the committee certifies {wo.wo_number} complete, only the advance of "
                                     f"{inr(wo.advance_amount)} agreed in it can be paid "
                                     f"({inr(pos['payable_now'])} more now)")
        if pos["retention_held"] > 0:
            due = self.retention_due_on(wo)
            raise HTTPException(422, f"{inr(pos['retention_held'])} ({wo.retention_pct}% retention) is held until "
                                     f"the defect liability period ends on {due:%d-%m-%Y}; "
                                     f"{inr(pos['payable_now'])} can be paid now")
        raise HTTPException(422, f"Only {inr(pos['payable_now'])} can be paid against {wo.wo_number} now")


class QuotationBook:
    """Quotations received, for a work order or a contract."""

    def __init__(self, db: Session):
        self.db = db

    def add(self, society_id: UUID, data: dict, user: User, existing: List[Quotation]) -> Quotation:
        vendor = self.db.get(Vendor, data["vendor_id"])
        if vendor is None or vendor.society_id != society_id or not vendor.is_active:
            raise HTTPException(422, "Vendor not found in this society")
        if vendor.status == VendorStatus.BLACKLISTED:
            raise HTTPException(422, f"{vendor.company_name} is blacklisted")
        if any(q.is_active and q.vendor_id == vendor.id for q in existing):
            raise HTTPException(409, f"A quotation from {vendor.company_name} is already recorded; "
                                     f"remove it to enter a revised one")
        _not_future(data["quotation_date"], "quotation date")
        if data.get("valid_until") and data["valid_until"] < data["quotation_date"]:
            raise HTTPException(422, "A quotation can't expire before its date")
        q = Quotation(society_id=society_id, received_by=user.id, **data)
        self.db.add(q)
        self.db.flush()
        return q


class ContractSanction:
    """Quotations and the sanction for an annual maintenance contract."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, contract_id: UUID, user: User) -> AMCContract:
        c = self.db.get(AMCContract, contract_id)
        if c is None or not c.is_active or (user.society_id is not None and c.society_id != user.society_id):
            raise HTTPException(404, "Contract not found")
        return c

    def add_quotation(self, contract_id: UUID, data: dict, user: User) -> Quotation:
        c = self.get(contract_id, user)
        if c.status != ContractStatus.DRAFT or c.sanctioned_at:
            raise HTTPException(409, "Quotations can be added while the contract is a draft not yet sanctioned")
        q = QuotationBook(self.db).add(c.society_id, data, user, existing=c.quotations)
        q.contract_id = c.id
        self.db.commit()
        self.db.refresh(q)
        return q

    def remove_quotation(self, contract_id: UUID, q_id: UUID, user: User) -> None:
        c = self.get(contract_id, user)
        if c.status != ContractStatus.DRAFT or c.sanctioned_at:
            raise HTTPException(409, "The contract was already sanctioned")
        q = next((q for q in c.quotations if q.id == q_id and q.is_active), None)
        if q is None:
            raise HTTPException(404, "Quotation not found")
        q.is_active = False
        self.db.commit()

    def sanction(self, contract_id: UUID, data: dict, user: User, request=None) -> AMCContract:
        c = self.get(contract_id, user)
        if c.status != ContractStatus.DRAFT or c.sanctioned_at:
            raise HTTPException(409, "Only a draft contract not yet sanctioned can be sanctioned")
        chosen = Sanction(self.db).apply(c, c.quotations, data, user)
        c.annual_value = money(chosen.total_amount)
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="vendor", entity_id=str(c.id),
                         entity_type="AMCContract", user=user, request=request,
                         new_values={"sanctioned": str(c.sanctioned_amount), "vendor": chosen.vendor.company_name,
                                     "level": c.sanction_level.value,
                                     "committee_resolution": c.committee_resolution_no,
                                     "gb_resolution": c.gb_resolution_no})
        self.db.commit()
        self.db.refresh(c)
        return c


def save_procurement_settings(db: Session, society_id: UUID, data: dict) -> dict:
    custom = data.get("committee_limit") is not None or data.get("tender_limit") is not None
    if custom and (not data.get("gb_resolution_no") or not data.get("gb_meeting_date")):
        raise HTTPException(422, "Limits other than the bye-law's are fixed by the general body: "
                                 "enter its resolution number and date")
    _not_future(data.get("gb_meeting_date"), "general body meeting date")
    s = db.query(ProcurementSettings).filter(ProcurementSettings.society_id == society_id).first()
    if s is None:
        s = ProcurementSettings(society_id=society_id)
        db.add(s)
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    return procurement_limits(db, society_id)


def work_order_out(db: Session, wo: WorkOrder, svc: Optional[WorkOrderService] = None) -> dict:
    svc = svc or WorkOrderService(db)
    pos = svc.money_position(wo)
    limits = procurement_limits(db, wo.society_id)
    live = [q for q in wo.quotations if q.is_active]
    basis = (money(wo.sanctioned_amount) if wo.sanctioned_amount is not None
             else money(min(q.total_amount for q in live)) if live
             else money(wo.estimated_cost) if wo.estimated_cost is not None else None)
    due = svc.retention_due_on(wo)
    return {
        "id": str(wo.id),
        "society_id": str(wo.society_id),
        "wo_number": wo.wo_number,
        "title": wo.title,
        "scope_of_work": wo.scope_of_work,
        "location": wo.location,
        "category": wo.category.value,
        "estimated_cost": str(wo.estimated_cost) if wo.estimated_cost is not None else None,
        "status": wo.status.value,
        "status_label": STATUS_LABEL[wo.status],
        "vendor_id": str(wo.vendor_id) if wo.vendor_id else None,
        "vendor_name": wo.vendor.company_name if wo.vendor else None,
        "service_request_id": str(wo.service_request_id) if wo.service_request_id else None,
        "complaint_id": str(wo.complaint_id) if wo.complaint_id else None,
        "asset_id": str(wo.asset_id) if wo.asset_id else None,
        "expense_account_id": str(wo.expense_account_id) if wo.expense_account_id else None,
        "expense_account_name": wo.expense_account.name if wo.expense_account else None,
        "start_date": wo.start_date.isoformat() if wo.start_date else None,
        "due_date": wo.due_date.isoformat() if wo.due_date else None,
        "payment_terms": wo.payment_terms,
        "advance_amount": str(wo.advance_amount),
        "retention_pct": str(wo.retention_pct),
        "defect_liability_months": wo.defect_liability_months,
        "issued_on": wo.issued_on.isoformat() if wo.issued_on else None,
        "completed_on": wo.completed_on.isoformat() if wo.completed_on else None,
        "completion_notes": wo.completion_notes,
        "certificate_ref": wo.certificate_ref,
        "certified_by_name": wo.certifier.full_name if wo.certifier else None,
        "retention_due_on": due.isoformat() if due else None,
        "retention_released_on": wo.retention_released_on.isoformat() if wo.retention_released_on else None,
        "closed_on": wo.closed_on.isoformat() if wo.closed_on else None,
        "cancel_reason": wo.cancel_reason,
        **sanction_out(wo),
        "quotations": quotations_out(wo.quotations),
        "requirements": requirements(limits, basis),
        "bills": [{
            "id": str(i.id), "invoice_number": i.invoice_number, "invoice_date": i.invoice_date.isoformat(),
            "total_amount": str(i.total_amount), "paid_amount": str(i.paid_amount),
            "outstanding": str(i.total_amount - i.paid_amount), "is_paid": i.is_paid,
        } for i in sorted(svc.bills(wo), key=lambda i: i.invoice_date)],
        "billed": str(pos["billed"]),
        "paid": str(pos["paid"]),
        "unbilled": str(pos["unbilled"]),
        "retention_amount": str(pos["retention"]),
        "retention_held": str(pos["retention_held"]),
        "payable_now": str(pos["payable_now"]),
        "created_at": wo.created_at.isoformat() if wo.created_at else None,
    }
