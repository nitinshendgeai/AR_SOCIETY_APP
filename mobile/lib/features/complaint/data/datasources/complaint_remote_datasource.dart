import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/api/paged.dart';
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

  /// GET /complaints/society/{societyId}, every page (the server sends 50 unless asked, 200 at most).
  Future<List<ComplaintListModel>> listSocietyComplaints(String societyId) async {
    final rows = await getAllPages(_dio, '/complaints/society/$societyId');
    return rows.map(ComplaintListModel.fromJson).toList();
  }

  /// GET /complaints/society/{societyId}/open-count - how many are still being dealt with (open, assigned, in
  /// progress or reopened): the same number the admin dashboard shows.
  Future<int> openComplaintsCount(String societyId) async {
    final r = await _dio.get('/complaints/society/$societyId/open-count');
    final n = (r.data as Map<String, dynamic>)['open'];
    if (n is! num) throw const FormatException('The open-complaints count is missing from the reply.');
    return n.toInt();
  }

  /// GET /complaints/me/open-count - how many of my complaints are still being dealt with (all of them).
  Future<int> myOpenComplaintsCount() async {
    final r = await _dio.get('/complaints/me/open-count');
    final n = (r.data as Map<String, dynamic>)['open'];
    if (n is! num) throw const FormatException('The open-complaints count is missing from the reply.');
    return n.toInt();
  }

  /// GET /complaints/me/complaints, every page.
  Future<List<ComplaintListModel>> listMyComplaints() async {
    final rows = await getAllPages(_dio, '/complaints/me/complaints');
    return rows.map(ComplaintListModel.fromJson).toList();
  }

  /// GET /complaints/me/assigned, every page.
  Future<List<ComplaintListModel>> listAssignedToMe() async {
    final rows = await getAllPages(_dio, '/complaints/me/assigned');
    return rows.map(ComplaintListModel.fromJson).toList();
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /// POST /complaints/{id}/assign
  Future<ComplaintModel> assignComplaint(
    String id, {
    required String assignedTo,
    String? dueDate,
    String? notes,
  }) async {
    final r = await _dio.post(
      '/complaints/$id/assign',
      data: {
        'assigned_to': assignedTo,
        if (dueDate != null) 'due_date': dueDate,
        if (notes != null) 'notes': notes,
      },
    );
    return ComplaintModel.fromJson(r.data as Map<String, dynamic>);
  }

  /// POST /complaints/{id}/reopen
  Future<ComplaintModel> reopenComplaint(String id, String reason) async {
    final r = await _dio.post('/complaints/$id/reopen', data: {'reason': reason});
    return ComplaintModel.fromJson(r.data as Map<String, dynamic>);
  }

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
