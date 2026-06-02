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

  // ── Staff ──────────────────────────────────────────────────────────────────

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
}
