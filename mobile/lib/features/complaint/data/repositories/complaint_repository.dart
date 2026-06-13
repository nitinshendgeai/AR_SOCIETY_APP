import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/complaint/data/datasources/complaint_remote_datasource.dart';
import 'package:ar_society_app/features/complaint/domain/entities/complaint_entities.dart';

// ── Result type ───────────────────────────────────────────────────────────────

sealed class ComplaintResult<T> {}

class ComplaintSuccess<T> extends ComplaintResult<T> {
  final T data;
  ComplaintSuccess(this.data);
}

class ComplaintFailure<T> extends ComplaintResult<T> {
  final String message;
  final int? statusCode;
  ComplaintFailure(this.message, {this.statusCode});
}

// ── Repository ────────────────────────────────────────────────────────────────

class ComplaintRepository {
  final ComplaintRemoteDataSource _ds;
  ComplaintRepository({ComplaintRemoteDataSource? ds})
      : _ds = ds ?? ComplaintRemoteDataSource();

  ComplaintResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      if (code == 409) {
        final detail =
            (e.response?.data as Map?)?['detail']?.toString() ?? '';
        return ComplaintFailure(
          detail.isNotEmpty ? detail : 'Action not allowed in current state',
          statusCode: 409,
        );
      }
      return ComplaintFailure(parseApiError(e), statusCode: code);
    }
    return ComplaintFailure('Unexpected error: $e');
  }

  // ── Create ─────────────────────────────────────────────────────────────────

  Future<ComplaintResult<ComplaintEntity>> createComplaint(
      Map<String, dynamic> data) async {
    try {
      final m = await _ds.createComplaint(data);
      return ComplaintSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Queries ────────────────────────────────────────────────────────────────

  Future<ComplaintResult<ComplaintEntity>> getComplaint(String id) async {
    try {
      final m = await _ds.getComplaint(id);
      return ComplaintSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ComplaintResult<List<ComplaintListEntity>>> listSocietyComplaints(
      String societyId) async {
    try {
      final list = await _ds.listSocietyComplaints(societyId);
      return ComplaintSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ComplaintResult<List<ComplaintListEntity>>> listMyComplaints() async {
    try {
      final list = await _ds.listMyComplaints();
      return ComplaintSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ComplaintResult<int>> openComplaintsCount(String societyId) async {
    try {
      final list = await _ds.listOpenComplaints(societyId);
      return ComplaintSuccess(list.length);
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  Future<ComplaintResult<ComplaintEntity>> updateStatus(
    String id,
    String status, {
    String? notes,
    String? resolutionNotes,
    String? rejectionReason,
  }) async {
    try {
      final m = await _ds.updateStatus(
        id,
        status: status,
        notes: notes,
        resolutionNotes: resolutionNotes,
        rejectionReason: rejectionReason,
      );
      return ComplaintSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<ComplaintResult<ComplaintCommentEntity>> addComment(
    String id,
    String body, {
    bool isInternal = false,
  }) async {
    try {
      final m = await _ds.addComment(id, body, isInternal: isInternal);
      return ComplaintSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }
}
