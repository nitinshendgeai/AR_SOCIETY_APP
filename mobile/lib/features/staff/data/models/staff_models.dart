import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';

// ── Designation model ─────────────────────────────────────────────────────────

class DesignationModel {
  final String id;
  final String societyId;
  final String name;
  final String department;
  final String? description;

  const DesignationModel({
    required this.id,
    required this.societyId,
    required this.name,
    required this.department,
    this.description,
  });

  factory DesignationModel.fromJson(Map<String, dynamic> j) => DesignationModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        name: j['name'] as String,
        department: j['department'] as String,
        description: j['description'] as String?,
      );

  DesignationEntity toEntity() => DesignationEntity(
        id: id, societyId: societyId, name: name,
        department: department, description: description,
      );
}

// ── Shift model ───────────────────────────────────────────────────────────────

class ShiftModel {
  final String id;
  final String societyId;
  final String name;
  final String shiftType;
  final String startTime;
  final String endTime;
  final bool isOvernight;

  const ShiftModel({
    required this.id,
    required this.societyId,
    required this.name,
    required this.shiftType,
    required this.startTime,
    required this.endTime,
    this.isOvernight = false,
  });

  factory ShiftModel.fromJson(Map<String, dynamic> j) => ShiftModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        name: j['name'] as String,
        shiftType: j['shift_type'] as String,
        startTime: j['start_time'] as String,
        endTime: j['end_time'] as String,
        isOvernight: j['is_overnight'] as bool? ?? false,
      );

  ShiftEntity toEntity() => ShiftEntity(
        id: id, societyId: societyId, name: name,
        shiftType: shiftType, startTime: startTime,
        endTime: endTime, isOvernight: isOvernight,
      );
}

// ── Staff model ───────────────────────────────────────────────────────────────

class StaffModel {
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

  const StaffModel({
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

  factory StaffModel.fromJson(Map<String, dynamic> j) => StaffModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        employeeCode: j['employee_code'] as String,
        fullName: j['full_name'] as String,
        mobile: j['mobile'] as String,
        department: j['department'] as String,
        status: j['status'] as String,
        shiftId: j['shift_id'] as String?,
        userId: j['user_id'] as String?,
        reportingManagerId: j['reporting_manager_id'] as String?,
        email: j['email'] as String?,
        joiningDate: j['joining_date'] as String?,
        designationId: j['designation_id'] as String?,
        designationName: j['designation_name'] as String?,
        reportingManagerName: j['reporting_manager_name'] as String?,
      );

  StaffEntity toEntity() => StaffEntity(
        id: id, societyId: societyId, employeeCode: employeeCode,
        fullName: fullName, mobile: mobile, department: department,
        status: status, shiftId: shiftId, userId: userId,
        reportingManagerId: reportingManagerId,
        email: email, joiningDate: joiningDate,
        designationId: designationId,
        designationName: designationName,
        reportingManagerName: reportingManagerName,
      );
}

// ── Attendance model ──────────────────────────────────────────────────────────

class AttendanceModel {
  final String id;
  final String staffId;
  final String societyId;
  final String attendanceDate;
  final String status;
  final String? checkInTime;
  final String? checkOutTime;
  final double? workingHours;
  final double? overtimeHours;
  final bool isManualEntry;
  final bool isApproved;
  final bool isCheckoutApproved;
  final String? notes;
  final String? staffName;

  const AttendanceModel({
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
    this.staffName,
  });

  factory AttendanceModel.fromJson(Map<String, dynamic> j) => AttendanceModel(
        id: j['id'] as String,
        staffId: j['staff_id'] as String,
        societyId: j['society_id'] as String,
        attendanceDate: j['attendance_date'] as String,
        status: j['status'] as String,
        checkInTime: j['check_in_time'] as String?,
        checkOutTime: j['check_out_time'] as String?,
        workingHours: (j['working_hours'] as num?)?.toDouble(),
        overtimeHours: (j['overtime_hours'] as num?)?.toDouble(),
        isManualEntry: j['is_manual_entry'] as bool? ?? false,
        isApproved: j['is_approved'] as bool? ?? false,
        isCheckoutApproved: j['is_checkout_approved'] as bool? ?? false,
        notes: j['notes'] as String?,
        staffName: j['staff_name'] as String?,
      );

  AttendanceEntity toEntity() => AttendanceEntity(
        id: id, staffId: staffId, societyId: societyId,
        attendanceDate: attendanceDate,
        status: AttendanceStatus.fromString(status),
        checkInTime: checkInTime != null ? DateTime.tryParse(checkInTime!) : null,
        checkOutTime: checkOutTime != null ? DateTime.tryParse(checkOutTime!) : null,
        workingHours: workingHours,
        overtimeHours: overtimeHours,
        isManualEntry: isManualEntry,
        isApproved: isApproved,
        isCheckoutApproved: isCheckoutApproved,
        notes: notes,
        staffName: staffName,
      );
}

// ── Duty model ────────────────────────────────────────────────────────────────

class DutyModel {
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
  final String? completedAt;
  final String? notes;

  const DutyModel({
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

  factory DutyModel.fromJson(Map<String, dynamic> j) => DutyModel(
        id: j['id'] as String,
        staffId: j['staff_id'] as String,
        societyId: j['society_id'] as String,
        dutyName: j['duty_name'] as String,
        description: j['description'] as String?,
        location: j['location'] as String?,
        dutyDate: j['duty_date'] as String,
        startTime: j['start_time'] as String?,
        endTime: j['end_time'] as String?,
        isCompleted: j['is_completed'] as bool? ?? false,
        isRecurring: j['is_recurring'] as bool? ?? false,
        completedAt: j['completed_at'] as String?,
        notes: j['notes'] as String?,
      );

  DutyEntity toEntity() => DutyEntity(
        id: id, staffId: staffId, societyId: societyId,
        dutyName: dutyName, description: description,
        location: location, dutyDate: dutyDate,
        startTime: startTime, endTime: endTime,
        isCompleted: isCompleted, isRecurring: isRecurring,
        completedAt: completedAt != null ? DateTime.tryParse(completedAt!) : null,
        notes: notes,
      );
}

// ── Handover models ───────────────────────────────────────────────────────────

class HandoverItemModel {
  final String id;
  final String itemType;
  final String title;
  final String? description;
  final bool isUrgent;
  final bool isResolved;
  final bool acknowledged;
  final int? quantity;

  const HandoverItemModel({
    required this.id,
    required this.itemType,
    required this.title,
    this.description,
    this.isUrgent = false,
    this.isResolved = false,
    this.acknowledged = false,
    this.quantity,
  });

  factory HandoverItemModel.fromJson(Map<String, dynamic> j) => HandoverItemModel(
        id: j['id'] as String,
        itemType: j['item_type'] as String,
        title: j['title'] as String,
        description: j['description'] as String?,
        isUrgent: j['is_urgent'] as bool? ?? false,
        isResolved: j['is_resolved'] as bool? ?? false,
        acknowledged: j['acknowledged'] as bool? ?? false,
        quantity: j['quantity'] as int?,
      );

  HandoverItemEntity toEntity() => HandoverItemEntity(
        id: id, itemType: itemType, title: title,
        description: description, isUrgent: isUrgent,
        isResolved: isResolved, acknowledged: acknowledged,
        quantity: quantity,
      );
}

class HandoverModel {
  final String id;
  final String societyId;
  final String? outgoingStaffId;
  final String? incomingStaffId;
  final String? area;
  final String summary;
  final String status;
  final List<HandoverItemModel> items;
  final String? acceptanceNotes;
  final String? disputeReason;
  final String? acceptedAt;
  final String createdAt;

  const HandoverModel({
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

  factory HandoverModel.fromJson(Map<String, dynamic> j) => HandoverModel(
        id: j['id'] as String,
        societyId: j['society_id'] as String,
        outgoingStaffId: j['outgoing_staff_id'] as String?,
        incomingStaffId: j['incoming_staff_id'] as String?,
        area: j['area'] as String?,
        summary: j['summary'] as String,
        status: j['status'] as String,
        items: (j['items'] as List<dynamic>? ?? [])
            .map((e) => HandoverItemModel.fromJson(e as Map<String, dynamic>))
            .toList(),
        acceptanceNotes: j['acceptance_notes'] as String?,
        disputeReason: j['dispute_reason'] as String?,
        acceptedAt: j['accepted_at'] as String?,
        createdAt: j['created_at'] as String,
      );

  HandoverEntity toEntity() => HandoverEntity(
        id: id, societyId: societyId,
        outgoingStaffId: outgoingStaffId,
        incomingStaffId: incomingStaffId,
        area: area, summary: summary,
        status: HandoverStatus.fromString(status),
        items: items.map((i) => i.toEntity()).toList(),
        acceptanceNotes: acceptanceNotes,
        disputeReason: disputeReason,
        acceptedAt: acceptedAt != null ? DateTime.tryParse(acceptedAt!) : null,
        createdAt: DateTime.parse(createdAt),
      );
}
