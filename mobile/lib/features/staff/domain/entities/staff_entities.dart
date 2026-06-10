// ── Designation entity ────────────────────────────────────────────────────────

class DesignationEntity {
  final String id;
  final String societyId;
  final String name;
  final String department;
  final String? description;

  const DesignationEntity({
    required this.id,
    required this.societyId,
    required this.name,
    required this.department,
    this.description,
  });
}

// ── Shift entity ──────────────────────────────────────────────────────────────

class ShiftEntity {
  final String id;
  final String societyId;
  final String name;
  final String shiftType;
  final String startTime;
  final String endTime;
  final bool isOvernight;

  const ShiftEntity({
    required this.id,
    required this.societyId,
    required this.name,
    required this.shiftType,
    required this.startTime,
    required this.endTime,
    this.isOvernight = false,
  });
}

// ── Staff entity ──────────────────────────────────────────────────────────────

class StaffEntity {
  final String id;
  final String societyId;
  final String employeeCode;
  final String fullName;
  final String mobile;
  final String department;
  final String status;
  final String? shiftId;
  final String? userId;
  final String? reportingManagerId;
  final String? email;
  final String? joiningDate;
  final String? designationId;
  final String? designationName;
  final String? reportingManagerName;

  const StaffEntity({
    required this.id,
    required this.societyId,
    required this.employeeCode,
    required this.fullName,
    required this.mobile,
    required this.department,
    required this.status,
    this.shiftId,
    this.userId,
    this.reportingManagerId,
    this.email,
    this.joiningDate,
    this.designationId,
    this.designationName,
    this.reportingManagerName,
  });

  String get departmentLabel {
    switch (department.toLowerCase()) {
      case 'security':     return 'Security';
      case 'housekeeping': return 'Housekeeping';
      case 'technical':    return 'Technical';
      case 'gym':          return 'Gym';
      case 'admin':        return 'Administration';
      default:             return department;
    }
  }
}

// ── Attendance status ─────────────────────────────────────────────────────────

enum AttendanceStatus {
  present,
  absent,
  halfDay,
  leave,
  overtime,
  offDuty;

  String get label {
    switch (this) {
      case AttendanceStatus.present:   return 'Present';
      case AttendanceStatus.absent:    return 'Absent';
      case AttendanceStatus.halfDay:   return 'Half Day';
      case AttendanceStatus.leave:     return 'On Leave';
      case AttendanceStatus.overtime:  return 'Overtime';
      case AttendanceStatus.offDuty:   return 'Off Duty';
    }
  }

  static AttendanceStatus fromString(String s) {
    switch (s.toLowerCase()) {
      case 'present':   return AttendanceStatus.present;
      case 'absent':    return AttendanceStatus.absent;
      case 'half_day':  return AttendanceStatus.halfDay;
      case 'leave':     return AttendanceStatus.leave;
      case 'overtime':  return AttendanceStatus.overtime;
      default:          return AttendanceStatus.offDuty;
    }
  }
}

// ── Attendance entity ─────────────────────────────────────────────────────────

class AttendanceEntity {
  final String id;
  final String staffId;
  final String societyId;
  final String attendanceDate;
  final AttendanceStatus status;
  final DateTime? checkInTime;
  final DateTime? checkOutTime;
  final double? workingHours;
  final double? overtimeHours;
  final bool isManualEntry;
  final bool isApproved;
  final bool isCheckoutApproved;
  final String? notes;

  const AttendanceEntity({
    required this.id,
    required this.staffId,
    required this.societyId,
    required this.attendanceDate,
    required this.status,
    this.checkInTime,
    this.checkOutTime,
    this.workingHours,
    this.overtimeHours,
    this.isManualEntry = false,
    this.isApproved = false,
    this.isCheckoutApproved = false,
    this.notes,
  });

  bool get isCheckedIn  => checkInTime != null;
  bool get isCheckedOut => checkOutTime != null;
  bool get isComplete   => isCheckedIn && isCheckedOut;
  bool get needsCheckinApproval  => isCheckedIn && !isApproved;
  bool get needsCheckoutApproval => isCheckedOut && !isCheckoutApproved;
}

// ── Duty entity ───────────────────────────────────────────────────────────────

class DutyEntity {
  final String id;
  final String staffId;
  final String societyId;
  final String dutyName;
  final String? description;
  final String? location;
  final String dutyDate;
  final String? startTime;
  final String? endTime;
  final bool isCompleted;
  final bool isRecurring;
  final DateTime? completedAt;
  final String? notes;

  const DutyEntity({
    required this.id,
    required this.staffId,
    required this.societyId,
    required this.dutyName,
    this.description,
    this.location,
    required this.dutyDate,
    this.startTime,
    this.endTime,
    required this.isCompleted,
    this.isRecurring = false,
    this.completedAt,
    this.notes,
  });
}

// ── Handover status ───────────────────────────────────────────────────────────

enum HandoverStatus {
  draft,
  submitted,
  accepted,
  disputed,
  verified,
  closed;

  String get label {
    switch (this) {
      case HandoverStatus.draft:     return 'Draft';
      case HandoverStatus.submitted: return 'Pending Acceptance';
      case HandoverStatus.accepted:  return 'Accepted';
      case HandoverStatus.disputed:  return 'Disputed';
      case HandoverStatus.verified:  return 'Verified';
      case HandoverStatus.closed:    return 'Closed';
    }
  }

  static HandoverStatus fromString(String s) {
    switch (s.toLowerCase()) {
      case 'submitted': return HandoverStatus.submitted;
      case 'accepted':  return HandoverStatus.accepted;
      case 'disputed':  return HandoverStatus.disputed;
      case 'verified':  return HandoverStatus.verified;
      case 'closed':    return HandoverStatus.closed;
      default:          return HandoverStatus.draft;
    }
  }
}

// ── Handover entity ───────────────────────────────────────────────────────────

class HandoverItemEntity {
  final String id;
  final String itemType;
  final String title;
  final String? description;
  final bool isUrgent;
  final bool isResolved;
  final bool acknowledged;
  final int? quantity;

  const HandoverItemEntity({
    required this.id,
    required this.itemType,
    required this.title,
    this.description,
    this.isUrgent = false,
    this.isResolved = false,
    this.acknowledged = false,
    this.quantity,
  });
}

class HandoverEntity {
  final String id;
  final String societyId;
  final String? outgoingStaffId;
  final String? incomingStaffId;
  final String? area;
  final String summary;
  final HandoverStatus status;
  final List<HandoverItemEntity> items;
  final String? acceptanceNotes;
  final String? disputeReason;
  final DateTime? acceptedAt;
  final DateTime createdAt;

  const HandoverEntity({
    required this.id,
    required this.societyId,
    this.outgoingStaffId,
    this.incomingStaffId,
    this.area,
    required this.summary,
    required this.status,
    required this.items,
    this.acceptanceNotes,
    this.disputeReason,
    this.acceptedAt,
    required this.createdAt,
  });

  bool get isPendingMyAction => status == HandoverStatus.submitted;
}
