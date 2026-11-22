from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List, Literal, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.resident import ResidentType
from app.schemas.resident import ResidentCreate, ResidentUpdate, ResidentOut, ResidentCreateOut
from app.schemas.resident_edit_request import (
    ResidentEditRequestCreate, ResidentEditRequestOut, ResidentEditRequestReject,
)
from app.services.resident_login_status import NEEDS_ATTENTION, resident_login_status
from app.services.flat_people_import import FamilyImportRequest, ImportResult
from app.services.resident_service import ResidentService
from app.services.resident_edit_request_service import ResidentEditRequestService
from app.services.resident_family_request_service import FamilyRequestService
from app.schemas.resident_family_request import FamilyRequestCreate, FamilyRequestOut, FamilyRequestReject
from app.core.dependencies import require_admin_committee, require_manager_above, get_current_user
from app.core.privacy import RESIDENT_PRIVATE_FIELDS, hide_private
from app.models.user import User

router = APIRouter(prefix="/residents", tags=["Residents"])


@router.post("/", response_model=ResidentCreateOut, status_code=201)
def create_resident(data: ResidentCreate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return ResidentService(db).create(data, current_user)


@router.get("/", response_model=List[ResidentOut])
def list_residents(
    flat_id: Optional[UUID] = None,
    wing_id: Optional[UUID] = None,
    resident_type: Optional[ResidentType] = None,
    is_active: Optional[bool] = True,
    moved_in: Optional[bool] = Query(None, description="true: living there now; false: no move-in date yet"),
    search: Optional[str] = Query(None, description="Matches name, phone, or email"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = ResidentService(db).list(
        current_user, flat_id=flat_id, resident_type=resident_type,
        is_active=is_active, search=search, skip=skip, limit=limit, wing_id=wing_id, moved_in=moved_in,
    )
    return [hide_private(r, current_user, RESIDENT_PRIVATE_FIELDS) for r in rows]


@router.get("/count", response_model=dict)
def count_residents(
    flat_id: Optional[UUID] = None,
    wing_id: Optional[UUID] = None,
    resident_type: Optional[ResidentType] = None,
    is_active: Optional[bool] = True,
    moved_in: Optional[bool] = Query(None, description="true: living there now; false: no move-in date yet"),
    search: Optional[str] = Query(None, description="Matches name, phone, or email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """How many residents match the same filters as the list (no paging): {"count": n}."""
    return {"count": ResidentService(db).count(
        current_user, flat_id=flat_id, resident_type=resident_type, is_active=is_active, search=search,
        wing_id=wing_id, moved_in=moved_in)}


REPORT_MAX_ROWS = 5000
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/family-import", response_model=List[ImportResult])
def import_family_file(data: FamilyImportRequest, db: Session = Depends(get_db),
                       current_user: User = Depends(require_admin_committee)):
    """Add family members and dependents to many flats from a sheet: one row per person, with their relationship, mobile
    and date of birth. They go on the flat's Residents list as Family or Dependent; no app login is made for them. A
    name already on the flat is skipped; a bad row is reported and the rest go in. `dry_run` (the default) checks every
    row and writes nothing."""
    from app.services.flat_people_import import import_family
    return import_family(db, data.rows, data.dry_run, current_user)


@router.get("/report-columns")
def report_columns(current_user: User = Depends(require_manager_above)):
    """The columns the Residents report can show, for the picker: key, label, whether it is in the default set, and
    whether it carries sensitive personal data."""
    from app.services.resident_report import catalog
    return catalog()


@router.get("/report")
def residents_report(
    format: Literal["pdf", "xlsx"] = "pdf",
    columns: Optional[str] = Query(None, description="Comma-separated column keys (see /residents/report-columns); empty: the default set"),
    flat_id: Optional[UUID] = None,
    wing_id: Optional[UUID] = None,
    resident_type: Optional[ResidentType] = None,
    is_active: Optional[bool] = True,
    moved_in: Optional[bool] = Query(None, description="true: living there now; false: no move-in date yet"),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_above),
):
    """The printed or downloaded Residents report: every resident the list would show for the same filters (no paging,
    up to 5,000), with only the chosen columns, as a PDF or an Excel file. Office roles only, because it can carry phone
    numbers and identity details; identity numbers are cut to their last four characters."""
    from app.models.flat import Flat
    from app.models.society import Society
    from app.models.wing import Wing
    from app.modules.billing.services.bill_pdf import flat_label
    from app.services import resident_report as rr

    try:
        chosen = rr.choose_columns(columns)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    residents = ResidentService(db).list(
        current_user, flat_id=flat_id, resident_type=resident_type, is_active=is_active, search=search,
        skip=0, limit=REPORT_MAX_ROWS, wing_id=wing_id, moved_in=moved_in,
    )
    flats = {f.id: f for f in db.query(Flat).filter(Flat.id.in_({r.flat_id for r in residents})).all()} if residents else {}
    rows = []
    for r in residents:
        d = r.model_dump()
        d.update({
            "flat": flat_label(flats.get(r.flat_id)), "name": r.full_name, "type": r.resident_type.value,
            "comm_preference": r.comm_preference.value if r.comm_preference else None,
        })
        rows.append(d)
    rows.sort(key=lambda x: (x["flat"], not x["is_primary"], x["name"].lower()))

    filters = ["current residents" if is_active else ("moved-out residents" if is_active is False else "current and moved out")]
    if wing_id:
        wing = db.query(Wing).filter(Wing.id == wing_id, Wing.society_id == current_user.society_id).first()
        filters.append(f"wing {wing.name}" if wing else "one wing")
    if flat_id and flats.get(flat_id):
        filters.append(f"flat {flat_label(flats[flat_id])}")
    if resident_type:
        filters.append(f"type {rr.TYPE_WORDS.get(resident_type.value, resident_type.value)}")
    if moved_in is not None:
        filters.append("moved in" if moved_in else "not moved in yet")
    if search and search.strip():
        filters.append(f'search "{search.strip()}"')

    society = db.query(Society).filter(Society.id == current_user.society_id).first()
    if format == "xlsx":
        return Response(content=rr.render_residents_xlsx(rows, chosen, filters, society), media_type=_XLSX,
                        headers={"Content-Disposition": "attachment; filename=Residents-Report.xlsx"})
    return Response(content=rr.render_residents_pdf(rows, chosen, filters, society), media_type="application/pdf",
                    headers={"Content-Disposition": "inline; filename=Residents-Report.pdf"})


@router.get("/login-status", response_model=dict)
def residents_login_status(
    status: Optional[Literal["linked", "login_disabled", "login_unlinked", "no_login", "no_mobile",
                             "needs_attention"]] = None,
    search: Optional[str] = Query(None, description="Matches name, flat or mobile"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_committee),
):
    """Which active residents can sign in to the app and which cannot (and why): the "Residents without a login"
    report. `status=needs_attention` is every resident who cannot sign in. The summary always counts the whole society."""
    if current_user.society_id is None:
        raise HTTPException(400, "Choose a society first")
    data = resident_login_status(db, current_user.society_id, None if status == "needs_attention" else status, search)
    if status == "needs_attention":
        data["residents"] = [r for r in data["residents"] if r["status"] in NEEDS_ATTENTION]
    return data


@router.get("/me", response_model=ResidentOut)
def get_my_resident_profile(flat_id: Optional[UUID] = None, db: Session = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    """My resident record; with several flats, `flat_id` picks which (default: the first)."""
    return ResidentService(db).get_me(current_user, flat_id)


@router.get("/mine", response_model=List[ResidentOut])
def list_my_flats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Every flat I am an active resident of, one record each."""
    return ResidentService(db).list_mine(current_user)


@router.get("/{resident_id}", response_model=ResidentOut)
def get_resident(resident_id: UUID, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return hide_private(ResidentService(db).get_or_404(resident_id, current_user), current_user, RESIDENT_PRIVATE_FIELDS)


@router.delete("/{resident_id}", status_code=204)
def delete_resident(resident_id: UUID, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    """Remove a resident entered by mistake. Refused (409, with the reason) once they have bills, gym visits, a parking
    allotment or have moved out: use Move out for someone who lived here."""
    ResidentService(db).delete(resident_id, current_user)


@router.patch("/{resident_id}", response_model=ResidentOut)
def update_resident(resident_id: UUID, data: ResidentUpdate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return ResidentService(db).update(resident_id, data, current_user)


# ── Self-service edit requests ─────────────────────────────────────────────
# A Resident cannot PATCH /residents/{id} directly (require_admin_committee
# above) — instead they submit a request here, which only takes effect once
# an Admin or Committee member approves it below.

@router.post("/edit-requests", response_model=ResidentEditRequestOut, status_code=201)
def create_edit_request(data: ResidentEditRequestCreate, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    return ResidentEditRequestService(db).create_request(data, current_user)


@router.get("/edit-requests/mine", response_model=List[ResidentEditRequestOut])
def list_my_edit_requests(db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    return ResidentEditRequestService(db).list_mine(current_user)


@router.get("/edit-requests/pending", response_model=List[ResidentEditRequestOut])
def list_pending_edit_requests(db: Session = Depends(get_db),
                                current_user: User = Depends(require_admin_committee)):
    return ResidentEditRequestService(db).list_pending(current_user.society_id)


@router.post("/edit-requests/{request_id}/approve", response_model=ResidentEditRequestOut)
def approve_edit_request(request_id: UUID, db: Session = Depends(get_db),
                          current_user: User = Depends(require_admin_committee)):
    return ResidentEditRequestService(db).approve(request_id, current_user)


@router.post("/edit-requests/{request_id}/reject", response_model=ResidentEditRequestOut)
def reject_edit_request(request_id: UUID, data: ResidentEditRequestReject, db: Session = Depends(get_db),
                         current_user: User = Depends(require_admin_committee)):
    return ResidentEditRequestService(db).reject(request_id, data.reason, current_user)


# ── Adding family members: the resident asks, the Admin or committee approves ────────────────────────────────────

@router.post("/family-requests", response_model=FamilyRequestOut, status_code=201)
def create_family_request(data: FamilyRequestCreate, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """An owner or co-owner asks to add a family member or dependent to their flat. Nothing is added until it is approved."""
    return FamilyRequestService(db).create(data, current_user)


@router.get("/family-requests/mine", response_model=List[FamilyRequestOut])
def list_my_family_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return FamilyRequestService(db).list_mine(current_user)


@router.get("/family-requests/pending", response_model=List[FamilyRequestOut])
def list_pending_family_requests(db: Session = Depends(get_db), current_user: User = Depends(require_admin_committee)):
    return FamilyRequestService(db).list_pending(current_user.society_id)


@router.post("/family-requests/{request_id}/approve", response_model=FamilyRequestOut)
def approve_family_request(request_id: UUID, db: Session = Depends(get_db),
                           current_user: User = Depends(require_admin_committee)):
    """Adds the person to the Residents list as Family or Dependent."""
    return FamilyRequestService(db).approve(request_id, current_user)


@router.post("/family-requests/{request_id}/reject", response_model=FamilyRequestOut)
def reject_family_request(request_id: UUID, data: FamilyRequestReject, db: Session = Depends(get_db),
                          current_user: User = Depends(require_admin_committee)):
    return FamilyRequestService(db).reject(request_id, data.reason, current_user)
