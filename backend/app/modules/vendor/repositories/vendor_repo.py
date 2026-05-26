from typing import List, Optional
from uuid import UUID
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.modules.vendor.models.vendor import (
    Vendor, VendorService, AMCContract, AMCServiceSchedule,
    ServiceRequest, ServiceVisitLog, VendorInvoice,
    VendorStatus, ContractStatus, ServiceRequestStatus,
)
from app.repositories.base import BaseRepository


class VendorRepo(BaseRepository[Vendor]):
    def __init__(self, db): super().__init__(Vendor, db)

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[Vendor]:
        return self.db.query(Vendor).filter(
            Vendor.society_id==sid, Vendor.is_active==True
        ).order_by(Vendor.company_name).offset(skip).limit(limit).all()

    def get_by_category(self, sid: UUID, category) -> List[Vendor]:
        return self.db.query(Vendor).filter(
            Vendor.society_id==sid, Vendor.category==category,
            Vendor.status==VendorStatus.ACTIVE, Vendor.is_active==True,
        ).all()

    def next_vendor_code(self, sid: UUID) -> str:
        from sqlalchemy import func
        count = self.db.query(func.count(Vendor.id)).filter(Vendor.society_id==sid).scalar() or 0
        return f"VND-{str(count+1).zfill(4)}"

    def get_by_gst(self, gst: str) -> Optional[Vendor]:
        return self.db.query(Vendor).filter(Vendor.gst_number==gst).first()


class AMCContractRepo(BaseRepository[AMCContract]):
    def __init__(self, db): super().__init__(AMCContract, db)

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[AMCContract]:
        return self.db.query(AMCContract).filter(
            AMCContract.society_id==sid, AMCContract.is_active==True
        ).order_by(AMCContract.end_date).offset(skip).limit(limit).all()

    def get_active_by_vendor(self, vendor_id: UUID) -> List[AMCContract]:
        return self.db.query(AMCContract).filter(
            AMCContract.vendor_id==vendor_id,
            AMCContract.status==ContractStatus.ACTIVE,
            AMCContract.is_active==True,
        ).all()

    def get_expiring(self, sid: UUID, days: int = 60) -> List[AMCContract]:
        cutoff = date.today() + timedelta(days=days)
        return self.db.query(AMCContract).filter(
            AMCContract.society_id==sid,
            AMCContract.status==ContractStatus.ACTIVE,
            AMCContract.end_date<=cutoff,
            AMCContract.end_date>=date.today(),
            AMCContract.is_active==True,
        ).order_by(AMCContract.end_date).all()

    def next_contract_number(self, sid: UUID) -> str:
        from sqlalchemy import func
        from datetime import date as dt
        count = self.db.query(func.count(AMCContract.id)).filter(AMCContract.society_id==sid).scalar() or 0
        return f"AMC-{dt.today().year}-{str(count+1).zfill(4)}"


class ServiceRequestRepo(BaseRepository[ServiceRequest]):
    def __init__(self, db): super().__init__(ServiceRequest, db)

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[ServiceRequest]:
        return self.db.query(ServiceRequest).filter(
            ServiceRequest.society_id==sid, ServiceRequest.is_active==True,
        ).order_by(ServiceRequest.created_at.desc()).offset(skip).limit(limit).all()

    def get_open(self, sid: UUID) -> List[ServiceRequest]:
        return self.db.query(ServiceRequest).filter(
            ServiceRequest.society_id==sid,
            ServiceRequest.status.in_([
                ServiceRequestStatus.OPEN, ServiceRequestStatus.ASSIGNED,
                ServiceRequestStatus.SCHEDULED, ServiceRequestStatus.IN_PROGRESS,
            ]),
            ServiceRequest.is_active==True,
        ).order_by(ServiceRequest.priority.desc()).all()

    def get_by_vendor(self, vendor_id: UUID, skip=0, limit=50) -> List[ServiceRequest]:
        return self.db.query(ServiceRequest).filter(
            ServiceRequest.vendor_id==vendor_id, ServiceRequest.is_active==True,
        ).order_by(ServiceRequest.created_at.desc()).offset(skip).limit(limit).all()

    def next_request_number(self, sid: UUID) -> str:
        from sqlalchemy import func
        count = self.db.query(func.count(ServiceRequest.id)).filter(
            ServiceRequest.society_id==sid
        ).scalar() or 0
        return f"SRQ-{str(count+1).zfill(5)}"
