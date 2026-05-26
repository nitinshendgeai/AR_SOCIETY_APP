from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.modules.parking.models.parking import (
    ParkingZone, ParkingFloor, ParkingSlot, ParkingAllocation,
    VisitorParking, ParkingViolation, ParkingAccessLog,
    SlotStatus, AllocationStatus, VisitorParkingStatus,
)
from app.repositories.base import BaseRepository
from datetime import datetime


class ParkingZoneRepo(BaseRepository[ParkingZone]):
    def __init__(self, db): super().__init__(ParkingZone, db)
    def get_by_society(self, sid: UUID) -> List[ParkingZone]:
        return self.db.query(ParkingZone).filter(ParkingZone.society_id==sid, ParkingZone.is_active==True).all()


class ParkingFloorRepo(BaseRepository[ParkingFloor]):
    def __init__(self, db): super().__init__(ParkingFloor, db)
    def get_by_zone(self, zone_id: UUID) -> List[ParkingFloor]:
        return self.db.query(ParkingFloor).filter(ParkingFloor.zone_id==zone_id, ParkingFloor.is_active==True).all()


class ParkingSlotRepo(BaseRepository[ParkingSlot]):
    def __init__(self, db): super().__init__(ParkingSlot, db)

    def get_by_zone(self, zone_id: UUID) -> List[ParkingSlot]:
        return self.db.query(ParkingSlot).filter(ParkingSlot.zone_id==zone_id, ParkingSlot.is_active==True).all()

    def get_available(self, society_id: UUID, slot_type=None) -> List[ParkingSlot]:
        q = self.db.query(ParkingSlot).filter(
            ParkingSlot.society_id==society_id,
            ParkingSlot.status==SlotStatus.AVAILABLE,
            ParkingSlot.is_active==True,
        )
        if slot_type: q = q.filter(ParkingSlot.slot_type==slot_type)
        return q.all()

    def get_by_number(self, society_id: UUID, slot_number: str) -> Optional[ParkingSlot]:
        return self.db.query(ParkingSlot).filter(
            ParkingSlot.society_id==society_id,
            ParkingSlot.slot_number==slot_number,
            ParkingSlot.is_active==True,
        ).first()


class ParkingAllocationRepo(BaseRepository[ParkingAllocation]):
    def __init__(self, db): super().__init__(ParkingAllocation, db)

    def get_active_by_slot(self, slot_id: UUID) -> Optional[ParkingAllocation]:
        return self.db.query(ParkingAllocation).filter(
            ParkingAllocation.slot_id==slot_id,
            ParkingAllocation.status==AllocationStatus.ACTIVE,
            ParkingAllocation.is_active==True,
        ).first()

    def get_active_by_flat(self, flat_id: UUID) -> List[ParkingAllocation]:
        return self.db.query(ParkingAllocation).filter(
            ParkingAllocation.flat_id==flat_id,
            ParkingAllocation.status==AllocationStatus.ACTIVE,
            ParkingAllocation.is_active==True,
        ).all()

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[ParkingAllocation]:
        return self.db.query(ParkingAllocation).filter(
            ParkingAllocation.society_id==sid, ParkingAllocation.is_active==True,
        ).offset(skip).limit(limit).all()


class VisitorParkingRepo(BaseRepository[VisitorParking]):
    def __init__(self, db): super().__init__(VisitorParking, db)

    def get_active_by_vehicle(self, society_id: UUID, vehicle_number: str) -> Optional[VisitorParking]:
        return self.db.query(VisitorParking).filter(
            VisitorParking.society_id==society_id,
            VisitorParking.vehicle_number==vehicle_number,
            VisitorParking.status==VisitorParkingStatus.ACTIVE,
            VisitorParking.is_active==True,
        ).first()

    def get_active(self, society_id: UUID) -> List[VisitorParking]:
        return self.db.query(VisitorParking).filter(
            VisitorParking.society_id==society_id,
            VisitorParking.status==VisitorParkingStatus.ACTIVE,
            VisitorParking.is_active==True,
        ).all()


class ParkingAccessLogRepo(BaseRepository[ParkingAccessLog]):
    def __init__(self, db): super().__init__(ParkingAccessLog, db)

    def get_by_vehicle(self, vehicle_number: str, skip=0, limit=50) -> List[ParkingAccessLog]:
        return self.db.query(ParkingAccessLog).filter(
            ParkingAccessLog.vehicle_number==vehicle_number,
        ).order_by(ParkingAccessLog.access_time.desc()).offset(skip).limit(limit).all()

    def get_by_society(self, sid: UUID, skip=0, limit=100) -> List[ParkingAccessLog]:
        return self.db.query(ParkingAccessLog).filter(
            ParkingAccessLog.society_id==sid,
        ).order_by(ParkingAccessLog.access_time.desc()).offset(skip).limit(limit).all()
