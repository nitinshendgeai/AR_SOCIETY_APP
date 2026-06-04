import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/features/visitor/data/datasources/visitor_remote_datasource.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';

// ── Result type ───────────────────────────────────────────────────────────────

sealed class VisitorResult<T> {}

class VisitorSuccess<T> extends VisitorResult<T> {
  final T data;
  VisitorSuccess(this.data);
}

class VisitorFailure<T> extends VisitorResult<T> {
  final String message;
  final int? statusCode;
  VisitorFailure(this.message, {this.statusCode});
}

// ── Repository ────────────────────────────────────────────────────────────────

class VisitorRepository {
  final VisitorRemoteDataSource _ds;
  VisitorRepository({VisitorRemoteDataSource? ds})
      : _ds = ds ?? VisitorRemoteDataSource();

  VisitorResult<T> _handle<T>(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      if (code == 409) {
        final detail =
            (e.response?.data as Map?)?['detail']?.toString() ?? '';
        return VisitorFailure(
          detail.isNotEmpty ? detail : 'Action not allowed in current state',
          statusCode: 409,
        );
      }
      return VisitorFailure(parseApiError(e), statusCode: code);
    }
    return VisitorFailure('Unexpected error: $e');
  }

  // ── Create ─────────────────────────────────────────────────────────────────

  Future<VisitorResult<VisitorEntity>> createVisitor(
      Map<String, dynamic> data) async {
    try {
      final m = await _ds.createVisitor(data);
      return VisitorSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  Future<VisitorResult<VisitorEntity>> approveVisitor(String id,
      {String? notes}) async {
    try {
      final m = await _ds.approveVisitor(id, notes: notes);
      return VisitorSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<VisitorResult<VisitorEntity>> rejectVisitor(
      String id, String reason) async {
    try {
      final m = await _ds.rejectVisitor(id, reason);
      return VisitorSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<VisitorResult<VisitorEntity>> checkIn(String id,
      {String? gateId, String? notes}) async {
    try {
      final m = await _ds.checkIn(id, gateId: gateId, notes: notes);
      return VisitorSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<VisitorResult<VisitorEntity>> checkOut(String id,
      {String? gateId, String? notes}) async {
    try {
      final m = await _ds.checkOut(id, gateId: gateId, notes: notes);
      return VisitorSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  // ── Queries ────────────────────────────────────────────────────────────────

  Future<VisitorResult<VisitorEntity>> getVisitor(String id) async {
    try {
      final m = await _ds.getVisitor(id);
      return VisitorSuccess(m.toEntity());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<VisitorResult<List<VisitorEntity>>> listSocietyVisitors(
      String societyId) async {
    try {
      final list = await _ds.listSocietyVisitors(societyId);
      return VisitorSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<VisitorResult<List<VisitorEntity>>> getPendingApprovals() async {
    try {
      final list = await _ds.getPendingApprovals();
      return VisitorSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }

  Future<VisitorResult<List<VisitorEntity>>> getMyVisitors() async {
    try {
      final list = await _ds.getMyVisitors();
      return VisitorSuccess(list.map((m) => m.toEntity()).toList());
    } catch (e) {
      return _handle(e);
    }
  }
}
