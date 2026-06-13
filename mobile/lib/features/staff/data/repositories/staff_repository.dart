import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/domain/entities/staff_entities.dart';

// ── Result type ───────────────────────────────────────────────────────────────

sealed class StaffResult<T> {}

class StaffSuccess<T> extends StaffResult<T> {
  final T data;
  StaffSuccess(this.data);
}

class StaffFailure<T> extends StaffResult<T> {
  final String message;
  final int? statusCode;
  StaffFailure(this.message, {this.statusCode});
}

// ── Repository ────────────────────────────────────────────────────────────────

class StaffRepository {
  final StaffRemoteDataSource _ds;
  StaffRepository({StaffRemoteDataSource? ds})
      : _ds = ds ?? StaffRemoteDataSource();

  StaffResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      // Map backend-specific codes to friendly messages
      if (code == 409) {
        final detail = (e.response?.data as Map?)?['detail']?.toString() ?? '';
        return StaffFailure(detail.isNotEmpty ? detail : 'Action not allowed in current state', statusCode: 409);
      }
      return StaffFailure(parseApiError(e), statusCode: code);
    }
    return StaffFailure('Unexpected error: $e');
  }

  // ── Staff CRUD ─────────────────────────────────────────────────────────────

  Future<StaffResult<StaffEntity>> getStaff(String staffId) async {
    try {
      final m = await _ds.getStaff(staffId);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<StaffEntity>> getStaffByUser(String userId) async {
    try {
      final m = await _ds.getStaffByUser(userId);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<StaffEntity>>> listStaff(String societyId, {String? department}) async {
    try {
      final list = await _ds.listStaff(societyId, department: department);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<StaffEntity>> createStaff(Map<String, dynamic> data) async {
    try {
      final m = await _ds.createStaff(data);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<StaffEntity>> updateStaff(String staffId, Map<String, dynamic> data) async {
    try {
      final m = await _ds.updateStaff(staffId, data);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  // ── Designations & Shifts ──────────────────────────────────────────────────

  Future<StaffResult<List<DesignationEntity>>> listDesignations(String societyId) async {
    try {
      final list = await _ds.listDesignations(societyId);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<ShiftEntity>>> listShifts(String societyId) async {
    try {
      final list = await _ds.listShifts(societyId);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  // ── Attendance ─────────────────────────────────────────────────────────────

  Future<StaffResult<AttendanceEntity>> checkIn(String staffId, {String? notes}) async {
    try {
      final m = await _ds.checkIn(staffId, notes: notes);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<AttendanceEntity>> checkOut(String staffId, {String? notes}) async {
    try {
      final m = await _ds.checkOut(staffId, notes: notes);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<AttendanceEntity>>> getAttendanceHistory(
    String staffId, {int skip = 0, int limit = 30}
  ) async {
    try {
      final list = await _ds.getAttendanceHistory(staffId, skip: skip, limit: limit);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<AttendanceEntity>>> getPendingAttendance(
    String societyId, {String? department}
  ) async {
    try {
      final list = await _ds.getPendingAttendance(societyId, department: department);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<AttendanceEntity>>> getPendingCheckout(
    String societyId, {String? department}
  ) async {
    try {
      final list = await _ds.getPendingCheckout(societyId, department: department);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<AttendanceEntity>> approveAttendance(String attendanceId, {String? notes}) async {
    try {
      final m = await _ds.approveAttendance(attendanceId, notes: notes);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<AttendanceEntity>> approveCheckout(String attendanceId, {String? notes}) async {
    try {
      final m = await _ds.approveCheckout(attendanceId, notes: notes);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<Map<String, dynamic>>> getAttendanceSummary(String societyId, String date) async {
    try {
      final data = await _ds.getAttendanceSummary(societyId, date);
      return StaffSuccess(data);
    } catch (e) { return _handle(e); }
  }

  // ── Duties ─────────────────────────────────────────────────────────────────

  Future<StaffResult<List<DutyEntity>>> getMyDuties(String staffId) async {
    try {
      final list = await _ds.getMyDuties(staffId);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<DutyEntity>> completeDuty(String dutyId) async {
    try {
      final m = await _ds.completeDuty(dutyId);
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<DutyEntity>> assignDuty({
    required String staffId,
    required String societyId,
    required String dutyName,
    required String dutyDate,
    String? description,
    String? location,
    String? startTime,
    String? endTime,
  }) async {
    try {
      final m = await _ds.assignDuty(
        staffId: staffId, societyId: societyId, dutyName: dutyName,
        dutyDate: dutyDate, description: description, location: location,
        startTime: startTime, endTime: endTime,
      );
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<DutyEntity>>> getDailyDuties(String societyId, String date) async {
    try {
      final list = await _ds.getDailyDuties(societyId, date);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<Map<String, dynamic>>> assignComplaintToDepartment({
    required String complaintId,
    required String department,
    String? notes,
  }) async {
    try {
      final data = await _ds.assignComplaintToDepartment(
        complaintId: complaintId, department: department, notes: notes);
      return StaffSuccess(data);
    } catch (e) { return _handle(e); }
  }

  // ── Handovers ──────────────────────────────────────────────────────────────

  Future<StaffResult<HandoverEntity>> createHandover({
    required String societyId,
    String? outgoingStaffId,
    String? incomingStaffId,
    String? area,
    required String summary,
    required List<Map<String, dynamic>> items,
  }) async {
    try {
      final m = await _ds.createHandover(
        societyId: societyId,
        outgoingStaffId: outgoingStaffId,
        incomingStaffId: incomingStaffId,
        area: area,
        summary: summary,
        items: items,
      );
      return StaffSuccess(m.toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<HandoverEntity>> submitHandover(String id) async {
    try {
      return StaffSuccess((await _ds.submitHandover(id)).toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<HandoverEntity>> acceptHandover(String id, {String? notes}) async {
    try {
      return StaffSuccess((await _ds.acceptHandover(id, notes: notes)).toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<HandoverEntity>> disputeHandover(String id, String reason) async {
    try {
      return StaffSuccess((await _ds.disputeHandover(id, reason)).toEntity());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<HandoverEntity>>> getPendingHandovers(String staffId) async {
    try {
      final list = await _ds.getPendingHandovers(staffId);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<List<HandoverEntity>>> getHandoverHistory(String staffId) async {
    try {
      final list = await _ds.getHandoverHistory(staffId);
      return StaffSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) { return _handle(e); }
  }

  // ── User account management ────────────────────────────────────────────────

  Future<StaffResult<Map<String, dynamic>>> getUserById(String userId) async {
    try {
      return StaffSuccess(await _ds.getUserById(userId));
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<String>> resetStaffPassword(String userId) async {
    try {
      return StaffSuccess(await _ds.resetUserPassword(userId));
    } catch (e) { return _handle(e); }
  }

  Future<StaffResult<bool>> setStaffLoginStatus(String userId, {required bool active}) async {
    try {
      await _ds.setUserStatus(userId, active ? 'active' : 'suspended');
      return StaffSuccess(true);
    } catch (e) { return _handle(e); }
  }
}
