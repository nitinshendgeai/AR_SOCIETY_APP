from app.models.society      import Society
from app.models.wing         import Wing
from app.models.flat         import Flat, FlatType, OccupancyStatus, MaintenanceStatus
from app.models.role         import Role
from app.models.user         import User, UserRole, UserStatus
from app.models.resident     import Resident, ResidentType, CommunicationPreference
from app.models.tenant       import Tenant, PoliceVerificationStatus
from app.models.vehicle      import Vehicle, VehicleType
from app.models.audit_log    import AuditLog, AuditAction
from app.models.notification import Notification, NotificationChannel, NotificationStatus, NotificationType

# Visitor module
from app.modules.visitor.models.visitor import Gate, Visitor, VisitorVehicle, VisitorLog, VisitorType, VisitorStatus, GateType

# Complaint module
from app.modules.complaint.models.complaint import (
    Complaint, ComplaintComment, ComplaintAttachment,
    ComplaintStatusHistory, ComplaintCategory, ComplaintPriority, ComplaintStatus,
)

# Amenity module
from app.modules.amenity.models.amenity import (
    Amenity, AmenityRule, AmenitySlot, AmenityPricing,
    AmenityBlackoutDate, AmenityBooking, AmenityUsageLog,
    AmenityType, BookingStatus, RuleType,
)

# Staff module
from app.modules.staff.models.staff import (
    Staff, StaffDesignation, StaffShift, DutyAssignment,
    StaffAttendance, StaffTask, StaffLeave, StaffWorkLog,
    StaffRoster, StaffLeaveBalance,
    StaffDepartment, StaffStatus, AttendanceStatus,
    TaskStatus, LeaveType, LeaveStatus, ShiftType, RosterStatus,
)

# Inventory module
from app.modules.inventory.models.inventory import (
    InventoryCategory, InventoryItem, InventoryStock,
    InventoryTransaction, InventoryIssue, InventoryReturn,
    Asset, AssetMaintenance, AssetAMC, AssetUsageLog,
    ItemCategory, UnitType, TransactionType, IssueStatus,
    AssetCategory, AssetStatus, MaintenanceType, MaintenanceStatus,
)

# Operational models
from app.models.occupancy_log     import OccupancyLog, OccupancyEventType
from app.models.agreement_tracker import AgreementTracker, AgreementStatus

# Payroll readiness models
from app.modules.staff.models.payroll_readiness import (
    StaffSalaryStructure, AttendanceCorrection, MonthlyAttendanceSummary,
    SalaryComponent, PayrollCycle, AttendanceCorrectionStatus,
)

# Parking module models
from app.modules.parking.models.parking import (
    ParkingZone, ParkingFloor, ParkingSlot, ParkingAllocation,
    VisitorParking, ParkingViolation, ParkingAccessLog,
    SlotType, SlotStatus, AllocationStatus, VisitorParkingStatus,
    ViolationType, AccessType, AccessMethod,
)

# Notice module models
from app.modules.notice.models.notice import (
    Notice, NoticeAcknowledgement, Announcement,
    CommunicationLog, EmergencyAlert,
    NoticeCategory, NoticePriority, NoticeStatus,
    AudienceType, AlertType, AlertStatus,
)

# Billing module models
from app.modules.billing.models.billing import (
    FinancialPeriod, MaintenanceChargeConfig, BillingCycle,
    MaintenanceBill, InvoiceLineItem, PaymentReceipt,
    DueTracker, PenaltyRule,
    ChargeType, BillStatus, PaymentMode, PenaltyCalculationType, CycleFrequency,
)
