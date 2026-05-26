"""
OccupancyService — manages flat occupancy lifecycle with validation.

Enforces:
- No two active residents/tenants in same flat at same time (primary constraint)
- Logs every move-in/out event to OccupancyLog
- Updates flat.occupancy_status automatically
"""
from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.flat import Flat, OccupancyStatus
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.occupancy_log import OccupancyLog, OccupancyEventType
from app.models.agreement_tracker import AgreementTracker, AgreementStatus
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.models.user import User
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class OccupancyService:

    def __init__(self, db: Session):
        self.db = db

    def _flat_or_404(self, flat_id: UUID) -> Flat:
        f = self.db.query(Flat).filter(Flat.id == flat_id, Flat.is_active == True).first()
        if not f: raise HTTPException(status_code=404, detail="Flat not found")
        return f

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
        flat = self._flat_or_404(flat_id)
        resident = self.db.query(Resident).filter(Resident.id == resident_id).first()
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
        flat = self._flat_or_404(flat_id)
        resident = self.db.query(Resident).filter(Resident.id == resident_id).first()
        if not resident: raise HTTPException(status_code=404, detail="Resident not found")

        resident.move_out_date = move_out_date
        resident.is_active     = False

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
        self.db.commit()
        return resident

    # ── Tenant move-in / move-out ─────────────────────────────────────────────

    def tenant_move_in(self, flat_id: UUID, tenant_id: UUID,
                        move_in_date: date, user: User,
                        create_agreement: bool = True) -> Tenant:
        flat = self._flat_or_404(flat_id)
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
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
                society_id=None, flat_id=flat_id, tenant_id=tenant_id,
                start_date=tenant.agreement_start_date,
                end_date=tenant.agreement_end_date,
                monthly_rent=tenant.monthly_rent,
                security_deposit=tenant.security_deposit,
                document_url=tenant.agreement_doc_url,
                created_by=user.id,
            )
            self.db.add(agr)

        self._log_event(flat, OccupancyEventType.TENANT_MOVE_IN, move_in_date,
                        user, tenant_id=tenant_id)
        self.db.commit()
        return tenant

    def tenant_move_out(self, flat_id: UUID, tenant_id: UUID,
                         move_out_date: date, user: User) -> Tenant:
        flat = self._flat_or_404(flat_id)
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant: raise HTTPException(status_code=404, detail="Tenant not found")

        tenant.move_out_date = move_out_date
        tenant.is_active     = False
        flat.occupancy_status = OccupancyStatus.VACANT

        # Terminate active agreement
        agr = self.db.query(AgreementTracker).filter(
            AgreementTracker.tenant_id == tenant_id,
            AgreementTracker.status    == AgreementStatus.ACTIVE,
        ).first()
        if agr:
            agr.status = AgreementStatus.TERMINATED
            agr.termination_reason = f"Tenant moved out on {move_out_date}"

        self._log_event(flat, OccupancyEventType.TENANT_MOVE_OUT, move_out_date,
                        user, tenant_id=tenant_id)
        self._log_event(flat, OccupancyEventType.FLAT_VACANT, move_out_date, user)
        self.db.commit()
        return tenant

    # ── Agreement expiry tracking ─────────────────────────────────────────────

    def get_expiring_agreements(self, society_id: UUID, days: int = 30) -> List[AgreementTracker]:
        from datetime import date as dt, timedelta
        cutoff = dt.today() + timedelta(days=days)
        return self.db.query(AgreementTracker).filter(
            AgreementTracker.society_id == society_id,
            AgreementTracker.status     == AgreementStatus.ACTIVE,
            AgreementTracker.end_date   <= cutoff,
        ).order_by(AgreementTracker.end_date).all()

    def get_flat_history(self, flat_id: UUID) -> List[OccupancyLog]:
        return self.db.query(OccupancyLog).filter(
            OccupancyLog.flat_id == flat_id
        ).order_by(OccupancyLog.event_date.desc()).all()
