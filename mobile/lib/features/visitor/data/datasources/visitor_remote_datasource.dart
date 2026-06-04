import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/visitor/data/models/visitor_models.dart';

/// Calls FastAPI /visitors/* endpoints.
class VisitorRemoteDataSource {
  final Dio _dio;
  VisitorRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  // ── Create ─────────────────────────────────────────────────────────────────

  /// POST /visitors/
  Future<VisitorModel> createVisitor(Map<String, dynamic> data) async {
    final r = await _dio.post('/visitors/', data: data);
    return VisitorModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /// POST /visitors/{id}/approve
  Future<VisitorModel> approveVisitor(String id, {String? notes}) async {
    final r = await _dio.post(
      '/visitors/$id/approve',
      data: {'notes': notes},
    );
    return VisitorModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /visitors/{id}/reject
  Future<VisitorModel> rejectVisitor(String id, String reason) async {
    final r = await _dio.post(
      '/visitors/$id/reject',
      data: {'reason': reason},
    );
    return VisitorModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /visitors/{id}/checkin
  Future<VisitorModel> checkIn(String id, {String? gateId, String? notes}) async {
    final r = await _dio.post(
      '/visitors/$id/checkin',
      data: {
        if (gateId != null) 'gate_id': gateId,
        if (notes != null) 'notes': notes,
      },
    );
    return VisitorModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /visitors/{id}/checkout
  Future<VisitorModel> checkOut(String id, {String? gateId, String? notes}) async {
    final r = await _dio.post(
      '/visitors/$id/checkout',
      data: {
        if (gateId != null) 'gate_id': gateId,
        if (notes != null) 'notes': notes,
      },
    );
    return VisitorModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Queries ────────────────────────────────────────────────────────────────

  /// GET /visitors/{id}
  Future<VisitorModel> getVisitor(String id) async {
    final r = await _dio.get('/visitors/$id');
    return VisitorModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /visitors/society/{societyId}?skip&limit
  Future<List<VisitorModel>> listSocietyVisitors(
    String societyId, {
    int skip = 0,
    int limit = 50,
  }) async {
    final r = await _dio.get(
      '/visitors/society/$societyId',
      queryParameters: {'skip': skip, 'limit': limit},
    );
    return (r.data as List)
        .map((e) => VisitorModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /visitors/me/pending-approvals
  Future<List<VisitorModel>> getPendingApprovals() async {
    final r = await _dio.get('/visitors/me/pending-approvals');
    return (r.data as List)
        .map((e) => VisitorModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /visitors/me/visitors?skip&limit
  Future<List<VisitorModel>> getMyVisitors({int skip = 0, int limit = 50}) async {
    final r = await _dio.get(
      '/visitors/me/visitors',
      queryParameters: {'skip': skip, 'limit': limit},
    );
    return (r.data as List)
        .map((e) => VisitorModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
