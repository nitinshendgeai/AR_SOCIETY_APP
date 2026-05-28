import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/staff/data/models/staff_models.dart';

/// Calls FastAPI /staff/* and /handovers/* endpoints.
/// API prefix: /api/v1/staff and /api/v1/handovers
class StaffRemoteDataSource {
  final Dio _dio;
  StaffRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  // ── Staff ──────────────────────────────────────────────────────────────────

  /// GET /staff/{staff_id}
  Future<StaffModel> getStaff(String staffId) async {
    final r = await _dio.get('/staff/$staffId');
    return StaffModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Attendance ─────────────────────────────────────────────────────────────

  /// POST /staff/attendance/{staff_id}/checkin
  Future<AttendanceModel> checkIn(String staffId, {String? notes}) async {
    final r = await _dio.post(
      '/staff/attendance/$staffId/checkin',
      data: {'notes': notes},
    );
    return AttendanceModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /staff/attendance/{staff_id}/checkout
  Future<AttendanceModel> checkOut(String staffId, {String? notes}) async {
    final r = await _dio.post(
      '/staff/attendance/$staffId/checkout',
      data: {'notes': notes},
    );
    return AttendanceModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /staff/attendance/{staff_id}?skip=0&limit=30
  Future<List<AttendanceModel>> getAttendanceHistory(
    String staffId, {
    int skip = 0,
    int limit = 30,
  }) async {
    final r = await _dio.get(
      '/staff/attendance/$staffId',
      queryParameters: {'skip': skip, 'limit': limit},
    );
    return (r.data as List)
        .map((e) => AttendanceModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Duties ─────────────────────────────────────────────────────────────────

  /// GET /staff/duties/me/{staff_id}
  Future<List<DutyModel>> getMyDuties(String staffId) async {
    final r = await _dio.get('/staff/duties/me/$staffId');
    return (r.data as List)
        .map((e) => DutyModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /staff/duties/{duty_id}/complete
  Future<DutyModel> completeDuty(String dutyId) async {
    final r = await _dio.post('/staff/duties/$dutyId/complete');
    return DutyModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Handovers ──────────────────────────────────────────────────────────────

  /// POST /handovers/
  Future<HandoverModel> createHandover({
    required String societyId,
    String? outgoingStaffId,
    String? incomingStaffId,
    String? area,
    required String summary,
    required List<Map<String, dynamic>> items,
  }) async {
    final r = await _dio.post('/handovers/', data: {
      'society_id': societyId,
      if (outgoingStaffId != null) 'outgoing_staff_id': outgoingStaffId,
      if (incomingStaffId != null) 'incoming_staff_id': incomingStaffId,
      if (area != null) 'area': area,
      'summary': summary,
      'items': items,
    });
    return HandoverModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /handovers/{id}/submit
  Future<HandoverModel> submitHandover(String handoverId) async {
    final r = await _dio.post('/handovers/$handoverId/submit');
    return HandoverModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /handovers/{id}/accept
  Future<HandoverModel> acceptHandover(String handoverId, {String? notes}) async {
    final r = await _dio.post(
      '/handovers/$handoverId/accept',
      data: {'notes': notes},
    );
    return HandoverModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /handovers/{id}/dispute
  Future<HandoverModel> disputeHandover(String handoverId, String reason) async {
    final r = await _dio.post(
      '/handovers/$handoverId/dispute',
      data: {'reason': reason},
    );
    return HandoverModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /handovers/pending/{staff_id}
  Future<List<HandoverModel>> getPendingHandovers(String staffId) async {
    final r = await _dio.get('/handovers/pending/$staffId');
    return (r.data as List)
        .map((e) => HandoverModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /handovers/staff/{staff_id}/history
  Future<List<HandoverModel>> getHandoverHistory(String staffId) async {
    final r = await _dio.get('/handovers/staff/$staffId/history');
    return (r.data as List)
        .map((e) => HandoverModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /handovers/{id}
  Future<HandoverModel> getHandover(String handoverId) async {
    final r = await _dio.get('/handovers/$handoverId');
    return HandoverModel.fromJson(r.data as Map<String, dynamic>);
  }
}
