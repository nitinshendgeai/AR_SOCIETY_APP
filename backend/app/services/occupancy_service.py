"""
OccupancyService — manages flat occupancy lifecycle with validation.

Enforces:
- No two active residents/tenants in same flat at same time (primary constraint)
- Logs every move-in/out event to OccupancyLog
- Updates flat.occupancy_status automatically
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.flat import Flat, OccupancyStatus
from app.models.wing import Wing
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.vehicle import Vehicle
from app.models.occupancy_log import OccupancyLog, OccupancyEventType
from app.models.agreement_tracker import AgreementTracker, AgreementStatus
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.models.user import User
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel
from app.core.tenant_scope import assert_society_access


class OccupancyService:

    def __init__(self, db: Session):
        self.db = db

    def _flat_or_404(self, flat_id: UUID, society_id: Optional[UUID] = None) -> Flat:
        """Fetch a flat, optionally requiring it belong to society_id (join
        through Wing — Flat has no society_id column of its own). Every
        move-in/move-out/history operation below routes through this so a
        caller can never act on another society's flat."""
        q = self.db.query(Flat).filter(Flat.id == flat_id, Flat.is_active == True)
        if society_id is not None:
            q = q.join(Wing, Flat.wing_id == Wing.id).filter(Wing.society_id == society_id)
        f = q.first()
        if not f: raise HTTPException(status_code=404, detail="Flat not found")
        return f

    def _unassign_vehicles(self, *, resident_id: UUID = None, tenant_id: UUID = None,
                           user: User = None) -> None:
        """On move-out, a Vehicle previously linked to this resident/tenant
        would otherwise keep silently pointing at a now-inactive person
        forever (Vehicle has no cascade/cleanup of its own). Unassign it —
        set the FK to NULL — without touching Vehicle.is_active; the vehicle
        itself hasn't gone anywhere, it's just no longer linked to anyone.
        Audits only when a vehicle was actually affected (avoids empty
        audit noise on every move-out, most of which have no vehicle)."""
        if resident_id is not None:
            vehicle_ids = [v.id for v in self.db.query(Vehicle.id).filter(
                Vehicle.resident_id == resident_id).all()]
            if vehicle_ids:
                self.db.query(Vehicle).filter(Vehicle.resident_id == resident_id).update(
                    {"resident_id": None}, synchronize_session=False
                )
                if user is not None:
                    AuditService.log(db=self.db, action=AuditAction.UPDATE, module="vehicle",
                                     entity_id=str(resident_id), entity_type="Resident", user=user,
                                     notes="Vehicle(s) unassigned on resident move-out",
                                     new_values={"vehicle_ids": [str(v) for v in vehicle_ids]})
        if tenant_id is not None:
            vehicle_ids = [v.id for v in self.db.query(Vehicle.id).filter(
                Vehicle.tenant_id == tenant_id).all()]
            if vehicle_ids:
                self.db.query(Vehicle).filter(Vehicle.tenant_id == tenant_id).update(
                    {"tenant_id": None}, synchronize_session=False
                )
                if user is not None:
                    AuditService.log(db=self.db, action=AuditAction.UPDATE, module="vehicle",
                                     entity_id=str(tenant_id), entity_type="Tenant", user=user,
                                     notes="Vehicle(s) unassigned on tenant move-out",
                                     new_values={"vehicle_ids": [str(v) for v in vehicle_ids]})

    def _log_event(self, flat: Flat, event_type: OccupancyEventType,
                   event_date: date, user: User,
                   resident_id: UUID = None, tenant_id: UUID = None, notes: str = None):
        log = OccupancyLog(
            society_id=flat.wing.society_id if hasattr(flat, 'wing') and flat.wing else None,
            flat_id=flat.id, wing_id=flat.wing_id,
            resident_id=resident_id, tenant_id=tenant_id,
            event_type=event_type, event_date=event_date,
            logged_by=user.id, notes=notes,
        )
        self.db.add(log)

    # ── Resident move-in ──────────────────────────────────────────────────────

    def resident_move_in(self, flat_id: UUID, resident_id: UUID,
                          move_in_date: date, user: User) -> Resident:
        flat = self._flat_or_404(flat_id, society_id=user.society_id)
        # Resident.flat_id is fixed at creation (residents never change flats
        # today — see Phase M1 audit), so requiring it to match flat_id both
        # confines this call to the caller's own society (via the scoped flat
        # lookup above) and rejects a mismatched resident/flat pair outright.
        resident = self.db.query(Resident).filter(
            Resident.id == resident_id, Resident.flat_id == flat_id,
        ).first()
        if not resident: raise HTTPException(status_code=404, detail="Resident not found")

        # Validate no active tenant if marking owner-occupied
        active_tenant = self.db.query(Tenant).filter(
            Tenant.flat_id == flat_id, Tenant.is_active == True,
            Tenant.move_out_date == None,
        ).first()
        if active_tenant and flat.occupancy_status == OccupancyStatus.TENANT_OCCUPIED:
            raise HTTPException(status_code=409,
                detail="Flat is currently tenant-occupied. Move out tenant first.")

        resident.move_in_date = move_in_date
        flat.occupancy_status = OccupancyStatus.OWNER_OCCUPIED
        self._log_event(flat, OccupancyEventType.RESIDENT_MOVE_IN, move_in_date,
                        user, resident_id=resident_id)
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="occupancy",
                         entity_id=str(flat_id), entity_type="Flat", user=user,
                         new_values={"event": "resident_move_in", "resident": str(resident_id),
                                     "date": str(move_in_date)})
        self.db.commit()
        return resident

    def resident_move_out(self, flat_id: UUID, resident_id: UUID,
                           move_out_date: date, user: User) -> Resident:
        flat = self._flat_or_404(flat_id, society_id=user.society_id)
        resident = self.db.query(Resident).filter(
            Resident.id == resident_id, Resident.flat_id == flat_id,
        ).first()
        if not resident: raise HTTPException(status_code=404, detail="Resident not found")

        resident.move_out_date = move_out_date
        resident.is_active     = False
        self._unassign_vehicles(resident_id=resident_id, user=user)

        # Check if any other residents remain
        remaining = self.db.query(Resident).filter(
            Resident.flat_id == flat_id, Resident.is_active == True,
            Resident.id != resident_id,
        ).count()
        if remaining == 0:
            flat.occupancy_status = OccupancyStatus.VACANT
            self._log_event(flat, OccupancyEventType.FLAT_VACANT, move_out_date, user)
        self._log_event(flat, OccupancyEventType.RESIDENT_MOVE_OUT, move_out_date,
                        user, resident_id=resident_id)
        # Phase M1.3: resident_move_in has always been audited; move_out was
        # not — closing that gap here, same event shape as move-in.
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="occupancy",
                         entity_id=str(flat_id), entity_type="Flat", user=user,
                         new_values={"event": "resident_move_out", "resident": str(resident_id),
                                     "date": str(move_out_date)})
        self.db.commit()
        return resident

    # ── Tenant move-in / move-out ─────────────────────────────────────────────

    def tenant_move_in(self, flat_id: UUID, tenant_id: UUID,
                        move_in_date: date, user: User,
                        create_agreement: bool = True) -> Tenant:
        flat = self._flat_or_404(flat_id, society_id=user.society_id)
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.flat_id == flat_id,
        ).first()
        if not tenant: raise HTTPException(status_code=404, detail="Tenant not found")

        # No double tenancy
        active_tenant = self.db.query(Tenant).filter(
            Tenant.flat_id == flat_id, Tenant.is_active == True,
            Tenant.move_out_date == None, Tenant.id != tenant_id,
        ).first()
        if active_tenant:
            raise HTTPException(status_code=409, detail="Another tenant is already active in this flat")

        tenant.move_in_date  = move_in_date
        flat.occupancy_status = OccupancyStatus.TENANT_OCCUPIED

        if create_agreement and tenant.agreement_start_date and tenant.agreement_end_date:
            # Check for overlapping active agreement
            overlap = self.db.query(AgreementTracker).filter(
                AgreementTracker.flat_id == flat_id,
                AgreementTracker.status  == AgreementStatus.ACTIVE,
                AgreementTracker.start_date <= tenant.agreement_end_date,
                AgreementTracker.end_date   >= tenant.agreement_start_date,
            ).first()
            if overlap:
                raise HTTPException(status_code=409,
                    detail="An active agreement overlaps with the specified dates")

            agr = AgreementTracker(
                society_id=flat.wing.society_id, flat_id=flat_id, tenant_id=tenant_id,
                start_date=tenant.agreement_start_date,
                end_date=tenant.agreement_end_date,
                monthly_rent=tenant.monthly_rent,
                security_deposit=tenant.security_deposit,
                document_url=tenant.agreement_doc_url,
                created_by=user.id,
            )
            self.db.add(agr)
            self.db.flush()
            AuditService.log(db=self.db, action=AuditAction.CREATE, module="agreement",
                             entity_id=str(agr.id), entity_type="AgreementTracker", user=user,
                             new_values={"tenant_id": str(tenant_id), "flat_id": str(flat_id),
                                         "start_date": str(agr.start_date), "end_date": str(agr.end_date)})

        self._log_event(flat, OccupancyEventType.TENANT_MOVE_IN, move_in_date,
                        user, tenant_id=tenant_id)
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="occupancy",
                         entity_id=str(flat_id), entity_type="Flat", user=user,
                         new_values={"event": "tenant_move_in", "tenant": str(tenant_id),
                                     "date": str(move_in_date)})
        self.db.commit()
        return tenant

    def tenant_move_out(self, flat_id: UUID, tenant_id: UUID,
                         move_out_date: date, user: User) -> Tenant:
        flat = self._flat_or_404(flat_id, society_id=user.society_id)
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.flat_id == flat_id,
        ).first()
        if not tenant: raise HTTPException(status_code=404, detail="Tenant not found")

        tenant.move_out_date = move_out_date
        tenant.is_active     = False
        flat.occupancy_status = OccupancyStatus.VACANT
        self._unassign_vehicles(tenant_id=tenant_id, user=user)

        # Terminate active agreement
        agr = self.db.query(AgreementTracker).filter(
            AgreementTracker.tenant_id == tenant_id,
            AgreementTracker.status    == AgreementStatus.ACTIVE,
        ).first()
        if agr:
            agr.status = AgreementStatus.TERMINATED
            agr.termination_reason = f"Tenant moved out on {move_out_date}"
            AuditService.log(db=self.db, action=AuditAction.UPDATE, module="agreement",
                             entity_id=str(agr.id), entity_type="AgreementTracker", user=user,
                             old_values={"status": "active"}, new_values={"status": "terminated"})

        self._log_event(flat, OccupancyEventType.TENANT_MOVE_OUT, move_out_date,
                        user, tenant_id=tenant_id)
        self._log_event(flat, OccupancyEventType.FLAT_VACANT, move_out_date, user)
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="occupancy",
                         entity_id=str(flat_id), entity_type="Flat", user=user,
                         new_values={"event": "tenant_move_out", "tenant": str(tenant_id),
                                     "date": str(move_out_date)})
        self.db.commit()
        return tenant

    # ── Agreement renewal ────────────────────────────────────────────────────

    def renew_agreement(self, tenant_id: UUID, new_start_date: date, new_end_date: date,
                         user: User, monthly_rent: Decimal = None,
                         security_deposit: Decimal = None, document_url: str = None) -> AgreementTracker:
        """Creates a new ACTIVE AgreementTracker linked via renewal_of_id to
        the tenant's current one, which moves to RENEWED (never deleted —
        Phase M1.3 §13). Keeps Tenant's cached "current terms" fields
        (agreement_start_date/end_date/monthly_rent/security_deposit) in
        sync with the new agreement, the same way tenant_move_in already
        keeps flat.occupancy_status in sync — Tenant holds current/intended
        state, AgreementTracker holds history (see the model's own
        docstring)."""
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        # Society check without leaking whether the tenant exists in another
        # society — cross-society renewal is structurally impossible since
        # every field written below is derived from this validated flat,
        # never from client input.
        flat = self._flat_or_404(tenant.flat_id, society_id=user.society_id)

        if new_end_date <= new_start_date:
            raise HTTPException(status_code=422, detail="end_date must be after start_date")

        current = self.db.query(AgreementTracker).filter(
            AgreementTracker.tenant_id == tenant_id,
            AgreementTracker.status    == AgreementStatus.ACTIVE,
        ).order_by(AgreementTracker.end_date.desc()).first()
        if not current:
            raise HTTPException(status_code=409, detail="Tenant has no active agreement to renew")

        # Same overlap-check shape as tenant_move_in, excluding the
        # agreement being renewed (it's about to become RENEWED).
        overlap = self.db.query(AgreementTracker).filter(
            AgreementTracker.flat_id == tenant.flat_id,
            AgreementTracker.status  == AgreementStatus.ACTIVE,
            AgreementTracker.id      != current.id,
            AgreementTracker.start_date <= new_end_date,
            AgreementTracker.end_date   >= new_start_date,
        ).first()
        if overlap:
            raise HTTPException(status_code=409,
                detail="Renewal dates overlap another active agreement on this flat")

        new_agr = AgreementTracker(
            society_id=flat.wing.society_id, flat_id=tenant.flat_id, tenant_id=tenant_id,
            start_date=new_start_date, end_date=new_end_date,
            monthly_rent=monthly_rent if monthly_rent is not None else current.monthly_rent,
            security_deposit=security_deposit if security_deposit is not None else current.security_deposit,
            document_url=document_url or current.document_url,
            renewal_of_id=current.id,
            status=AgreementStatus.ACTIVE,
            created_by=user.id,
        )
        self.db.add(new_agr)
        self.db.flush()

        current.status = AgreementStatus.RENEWED

        tenant.agreement_start_date = new_start_date
        tenant.agreement_end_date   = new_end_date
        if monthly_rent is not None:
            tenant.monthly_rent = monthly_rent
        if security_deposit is not None:
            tenant.security_deposit = security_deposit

        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="agreement",
                         entity_id=str(current.id), entity_type="AgreementTracker", user=user,
                         old_values={"status": "active"},
                         new_values={"status": "renewed", "renewed_by": str(new_agr.id)})
        AuditService.log(db=self.db, action=AuditAction.CREATE, module="agreement",
                         entity_id=str(new_agr.id), entity_type="AgreementTracker", user=user,
                         new_values={"tenant_id": str(tenant_id), "renewal_of_id": str(current.id),
                                     "start_date": str(new_start_date), "end_date": str(new_end_date)})
        self.db.commit()
        self.db.refresh(new_agr)
        return new_agr

    # ── Agreement expiry tracking ─────────────────────────────────────────────

    def get_expiring_agreements(self, society_id: UUID, days: int,
                                 current_user: User) -> List[AgreementTracker]:
        assert_society_access(current_user, society_id)
        from datetime import date as dt, timedelta
        cutoff = dt.today() + timedelta(days=days)
        return self.db.query(AgreementTracker).filter(
            AgreementTracker.society_id == society_id,
            AgreementTracker.status     == AgreementStatus.ACTIVE,
            AgreementTracker.end_date   <= cutoff,
        ).order_by(AgreementTracker.end_date).all()

    def get_flat_history(self, flat_id: UUID, current_user: User) -> List[OccupancyLog]:
        self._flat_or_404(flat_id, society_id=current_user.society_id)
        return self.db.query(OccupancyLog).filter(
            OccupancyLog.flat_id == flat_id
        ).order_by(OccupancyLog.event_date.desc()).all()
