from app.models.society      import Society
from app.models.wing         import Wing
from app.models.flat         import Flat, FlatType, OccupancyStatus
from app.models.role         import Role
from app.models.user         import User, UserRole, UserStatus
from app.models.resident     import Resident, ResidentType
from app.models.tenant       import Tenant
from app.models.audit_log    import AuditLog, AuditAction
from app.models.notification import Notification, NotificationChannel, NotificationStatus, NotificationType
# Visitor module models
from app.modules.visitor.models.visitor import Gate, Visitor, VisitorVehicle, VisitorLog, VisitorType, VisitorStatus, GateType

__all__ = [
    "Society", "Wing", "Flat", "FlatType", "OccupancyStatus",
    "Role", "User", "UserRole", "UserStatus",
    "Resident", "ResidentType", "Tenant",
    "AuditLog", "AuditAction",
    "Notification", "NotificationChannel", "NotificationStatus", "NotificationType",
    "Gate", "Visitor", "VisitorVehicle", "VisitorLog", "VisitorType", "VisitorStatus", "GateType",
]

# Complaint module models
from app.modules.complaint.models.complaint import (
    Complaint, ComplaintComment, ComplaintAttachment,
    ComplaintStatusHistory, ComplaintCategory, ComplaintPriority, ComplaintStatus,
)
