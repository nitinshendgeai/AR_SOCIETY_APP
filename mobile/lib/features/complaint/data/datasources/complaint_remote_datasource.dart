import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/complaint/data/models/complaint_models.dart';

/// Calls FastAPI /complaints/* endpoints.
class ComplaintRemoteDataSource {
  final Dio _dio;
  ComplaintRemoteDataSource({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  // ── Create ─────────────────────────────────────────────────────────────────

  /// POST /complaints/
  Future<ComplaintModel> createComplaint(Map<String, dynamic> data) async {
    final r = await _dio.post('/complaints/', data: data);
    return ComplaintModel.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Queries ────────────────────────────────────────────────────────────────

  /// GET /complaints/{id}
  Future<ComplaintModel> getComplaint(String id) async {
    final r = await _dio.get('/complaints/$id');
    return ComplaintModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// GET /complaints/society/{societyId}?skip&limit
  Future<List<ComplaintListModel>> listSocietyComplaints(
    String societyId, {
    int skip = 0,
    int limit = 50,
  }) async {
    final r = await _dio.get(
      '/complaints/society/$societyId',
      queryParameters: {'skip': skip, 'limit': limit},
    );
    return (r.data as List)
        .map((e) => ComplaintListModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /complaints/society/{societyId}/open
  Future<List<ComplaintListModel>> listOpenComplaints(String societyId) async {
    final r = await _dio.get('/complaints/society/$societyId/open');
    return (r.data as List)
        .map((e) => ComplaintListModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /complaints/me/complaints?skip&limit
  Future<List<ComplaintListModel>> listMyComplaints({
    int skip = 0,
    int limit = 50,
  }) async {
    final r = await _dio.get(
      '/complaints/me/complaints',
      queryParameters: {'skip': skip, 'limit': limit},
    );
    return (r.data as List)
        .map((e) => ComplaintListModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /// POST /complaints/{id}/status
  Future<ComplaintModel> updateStatus(
    String id, {
    required String status,
    String? notes,
    String? resolutionNotes,
    String? rejectionReason,
  }) async {
    final r = await _dio.post(
      '/complaints/$id/status',
      data: {
        'status': status,
        if (notes != null) 'notes': notes,
        if (resolutionNotes != null) 'resolution_notes': resolutionNotes,
        if (rejectionReason != null) 'rejection_reason': rejectionReason,
      },
    );
    return ComplaintModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /complaints/{id}/comments
  Future<ComplaintCommentModel> addComment(
    String id,
    String body, {
    bool isInternal = false,
  }) async {
    final r = await _dio.post(
      '/complaints/$id/comments',
      data: {'body': body, 'is_internal': isInternal},
    );
    return ComplaintCommentModel.fromJson(r.data as Map<String, dynamic>);
  }
}
